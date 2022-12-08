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

from tests.e2e import run_app


@pytest.mark.e2e
def test_recreate_running_env(
    composer_image_version,
    composer_image_version_older,
    valid_project_id,
    env_name,
):
    default_port, new_port = "8080", "8085"
    create_cmd = (
        "create --from-image-version {version} "
        "-p {project} --port {port} {env_name}"
    )
    create_cmd_default = create_cmd.format(
        version=composer_image_version,
        project=valid_project_id,
        port=default_port,
        env_name=env_name,
    )
    create_cmd_new_version_port = create_cmd.format(
        version=composer_image_version_older,
        project=valid_project_id,
        port=new_port,
        env_name=env_name,
    )
    exp_describe = (
        "Composer {env_name} environment is in state: running. "
        "Web-server can be accessed at http://localhost:{port} "
        "Image version: {version}"
    )
    exp_describe_initial = exp_describe.format(
        env_name=env_name, port=default_port, version=composer_image_version
    )
    exp_describe_recreated = exp_describe.format(
        env_name=env_name,
        port=default_port,
        version=composer_image_version_older,
    )
    exp_describe_restarted = exp_describe.format(
        env_name=env_name, port=new_port, version=composer_image_version_older
    )

    run_app(create_cmd_default)
    run_app(f"start {env_name}")
    run_app(f"describe {env_name}", expected_output=exp_describe_initial)
    run_app(create_cmd_new_version_port, input="y")
    run_app(f"describe {env_name}", expected_output=exp_describe_recreated)
    run_app("restart")
    run_app(f"describe {env_name}", expected_output=exp_describe_restarted)
    run_app(f"stop {env_name}")
