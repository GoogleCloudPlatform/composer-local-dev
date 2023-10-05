#!/bin/sh"

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

sudo chown airflow:airflow airflow

mkdir -p ${AIRFLOW__CORE__DAGS_FOLDER}
mkdir -p ${AIRFLOW__CORE__PLUGINS_FOLDER}

# That file exists in Composer < 1.19.2 and is responsible for linking name
# `python` to python3 exec, in Composer >= 1.19.2 name `python` is already
# linked to python3 and file no longer exist.
if [ -f /var/local/setup_python_command.sh ]; then
  /var/local/setup_python_command.sh
fi

if [ -n "${PRIVATE_INDEX_URLS}" ]; then
  echo "Adding private PyPI repository indexes: ${PRIVATE_INDEX_URLS}"
  pip3 install keyring keyrings.google-artifactregistry-auth

  # Split PRIVATE_INDEX_URLS by comma and create a space-separated string of URLs
  IFS=',' read -ra URLS_ARRAY <<<"${PRIVATE_INDEX_URLS}"
  EXTRA_INDEX_URLS=""
  for url in "${URLS_ARRAY[@]}"; do
    EXTRA_INDEX_URLS+=" --extra-index-url ${url}"
  done

  # Use the URLs in pip config set
  pip3 config set global.extra-index-url "${EXTRA_INDEX_URLS}"
fi

pip3 install --upgrade -r composer_requirements.txt
pip3 check

airflow db init

# Allow non-authenticated access to UI for Airflow 2.*
if ! grep -Fxq "AUTH_ROLE_PUBLIC = 'Admin'" /home/airflow/airflow/webserver_config.py; then
  echo "AUTH_ROLE_PUBLIC = 'Admin'" >>/home/airflow/airflow/webserver_config.py
fi

airflow scheduler &
exec airflow webserver
