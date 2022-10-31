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

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

DAG_ID = "example_dag"
RANDOM_FILE_NAME = "random.bin"


with DAG(
    dag_id=DAG_ID,
    schedule_interval="@once",
    start_date=datetime(2021, 1, 1),
) as dag:
    op = BashOperator(
        task_id="task",
        bash_command=f"cat /dev/urandom | head -c $((1 * 1024 * 1024)) > {RANDOM_FILE_NAME}",
    )
