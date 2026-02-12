#!/bin/bash

# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -xe

FAST_API_DIR=/opt/python3.11/lib/python3.11/site-packages/airflow/api_fastapi/

run_as_user=/home/airflow/run_as_user.sh

get_airflow_version() {
  airflow_version=$(${run_as_user} airflow version 2>/dev/null | grep -oE '[0-9]\.[0-9]+\.[0-9]+' | head -1)
  original_ifs="$IFS"
  IFS='.'
  set -- $airflow_version
  major="$1"
  minor="$2"
  patch="$3"
  IFS="$original_ifs"
  echo "$major" "$minor" "$patch"
}

init_airflow() {

  $run_as_user mkdir -p ${AIRFLOW__CORE__DAGS_FOLDER}
  $run_as_user mkdir -p ${AIRFLOW__CORE__PLUGINS_FOLDER}
  $run_as_user mkdir -p ${AIRFLOW__CORE__DATA_FOLDER}

  # That file exists in Composer < 1.19.2 and is responsible for linking name
  # `python` to python3 exec, in Composer >= 1.19.2 name `python` is already
  # linked to python3 and file no longer exist.
  if [ -f /var/local/setup_python_command.sh ]; then
      $run_as_user /var/local/setup_python_command.sh
  fi

  sudo pip3 install --upgrade -r composer_requirements.txt
  sudo pip3 check

  airflow_version=($(get_airflow_version))
  major="${airflow_version[0]}"
  minor="${airflow_version[1]}"

  if [ "$major" -eq "3" ]; then
    $run_as_user cp -r /etc/airflow/config /home/airflow/airflow/config
  else
    # Allow non-authenticated access to UI for Airflow 2.*
    if ! grep -Fxq "AUTH_ROLE_PUBLIC = 'Admin'" /home/airflow/airflow/webserver_config.py; then
      $run_as_user sh -c "echo \"AUTH_ROLE_PUBLIC = 'Admin'\" >> /home/airflow/airflow/webserver_config.py"
    fi
  fi

  if [ "$major" -eq "2" ] && [ "$minor" -lt "7" ]; then
    $run_as_user airflow db init
  else
    $run_as_user airflow db migrate
  fi
}

create_user() {
  local user_name="$1"
  local user_id="$2"

  local old_user_name
  old_user_name="$(whoami)"
  local old_user_id
  old_user_id="$(id -u)"

  echo "Adding user ${user_name}(${user_id})"
  sudo useradd -m -r -g airflow -G airflow --home-dir /home/airflow \
    -u "${user_id}" -o "${user_name}"

  echo "Updating the owner of the dirs owned by ${old_user_name}(${old_user_id}) to ${user_name}(${user_id})"
  sudo find /home -user "${old_user_id}" -exec chown -h "${user_name}" {} \;
  sudo find /var -user "${old_user_id}" -exec chown -h "${user_name}" {} \;
  if [ -d "$FAST_API_DIR" ]; then
  sudo find $FAST_API_DIR -user "${old_user_id}" \
    -exec chown -h -R "${user_name}" {} \;
  fi
}

main() {
  sudo chown airflow:airflow airflow
  sudo chmod +x $run_as_user

  if [[ -n "$PGDATA" ]]; then
    sudo chmod -R o+xrw $PGDATA
  fi

  # In Airflow 3, the airflow process needs access to create files in FAST_API_DIR
  # when using the SimpleAuthManager
  if [ -d "$FAST_API_DIR" ]; then
    sudo chown -R airflow:airflow "$FAST_API_DIR"
  fi

  if [ "${COMPOSER_CONTAINER_RUN_AS_HOST_USER}" = "True" ]; then
    create_user "${COMPOSER_HOST_USER_NAME}" "${COMPOSER_HOST_USER_ID}" || true
    echo "Running Airflow as user ${COMPOSER_HOST_USER_NAME}(${COMPOSER_HOST_USER_ID})"
  else
    echo "Running Airflow as user airflow(999)"
  fi

  airflow_version=($(get_airflow_version))
  major="${airflow_version[0]}"

  init_airflow

  $run_as_user airflow scheduler &
  $run_as_user airflow triggerer &

  if [[ "$major" -eq "3" || ${AIRFLOW__SCHEDULER__STANDALONE_DAG_PROCESSOR} = "True" ]]; then
    $run_as_user airflow dag-processor &
  fi

  if [ "$major" -eq "3" ]; then
    $run_as_user airflow api-server --apps execution -p 8081 --workers 1 &
    exec $run_as_user airflow api-server --apps core
  else
    exec $run_as_user airflow webserver
  fi
}

main "$@"
