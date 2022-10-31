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
import pytest

from tests.e2e import assert_example_dag_listed, run_app, run_cmd


@pytest.mark.e2e
def test_run_in_killed_container(valid_version, valid_project_id, env_name):
    run_app(
        f"create --from-image-version {valid_version} "
        f"-p {valid_project_id} {env_name}"
    )
    run_app(f"start {env_name}")
    run_cmd(f"docker kill composer-local-dev-{env_name}")
    run_app(f"logs {env_name}")
    run_app(
        f"run-airflow-cmd {env_name} dags list",
        exit_code=1,
        expected_output="Failed to run command: environment not running.",
    )
