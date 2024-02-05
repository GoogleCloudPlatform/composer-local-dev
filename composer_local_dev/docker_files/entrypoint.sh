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

pip3 install --upgrade -r composer_requirements.txt
pip3 check

export PATH="$PATH:/home/airflow/.local/bin"

# Install mysql-server if does't exist
sudo apt-get update
sudo apt install mysql-server -y
sudo service mysql stop
sudo service mysql start
sudo mysql -e " CREATE DATABASE IF NOT EXISTS airflow_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mysql -e "CREATE USER IF NOT EXISTS 'airflow_user' IDENTIFIED BY 'airflow_pass';"
sudo mysql -e "GRANT ALL PRIVILEGES ON airflow_db.* TO 'airflow_user';"

airflow db init

# Allow non-authenticated access to UI for Airflow 2.*
if ! grep -Fxq "AUTH_ROLE_PUBLIC = 'Admin'" /home/airflow/airflow/webserver_config.py; then
  echo "AUTH_ROLE_PUBLIC = 'Admin'" >> /home/airflow/airflow/webserver_config.py
fi

airflow scheduler &
exec airflow webserver
