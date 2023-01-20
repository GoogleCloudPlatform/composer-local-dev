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

# Workaround for Airflow not being able to read bind mounted gcloud configuration.
mkdir -p .config/gcloud
sudo cp gcloud/application_default_credentials.json .config/gcloud/
sudo chmod +r .config/gcloud/application_default_credentials.json

# That file exists in Composer < 1.19.2 and is responsible for linking name
# `python` to python3 exec, in Composer >= 1.19.2 name `python` is already
# linked to python3 and file no longer exist.
if [ -f /var/local/setup_python_command.sh ]; then
    /var/local/setup_python_command.sh
fi

pip3 install --upgrade -r composer_requirements.txt
pip3 check

airflow db init

# Allow non-authenticated access to UI for Airflow 2.*
if ! grep -Fxq "AUTH_ROLE_PUBLIC = 'Admin'" /home/airflow/airflow/webserver_config.py; then
  echo "AUTH_ROLE_PUBLIC = 'Admin'" >> /home/airflow/airflow/webserver_config.py
fi

airflow scheduler &
exec airflow webserver
