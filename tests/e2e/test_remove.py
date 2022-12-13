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
import pathlib

import pytest

from composer_local_dev import constants
from tests.e2e import run_app


@pytest.mark.e2e
def test_remove(env_name, composer_image_version, valid_project_id):
    env_dir = pathlib.Path("composer") / env_name
    run_app(
        f"create --from-image-version {composer_image_version} "
        f"-p {valid_project_id} {env_name}"
    )
    assert env_dir.exists()
    run_app(f"remove {env_name}", input="y")
    assert not env_dir.exists()


@pytest.mark.e2e
def test_require_confirmation(
    env_name, composer_image_version, valid_project_id
):
    env_dir = pathlib.Path("composer") / env_name
    run_app(
        f"create --from-image-version {composer_image_version} "
        f"-p {valid_project_id} {env_name}"
    )
    assert env_dir.exists()
    run_app(f"remove {env_name}", exit_code=1)  # no input provided
    assert env_dir.exists()


@pytest.mark.e2e
def test_skip_confirmation_flag(
    env_name, composer_image_version, valid_project_id
):
    env_dir = pathlib.Path("composer") / env_name
    run_app(
        f"create --from-image-version {composer_image_version} "
        f"-p {valid_project_id} {env_name}"
    )
    assert env_dir.exists()
    run_app(f"remove {env_name} --skip-confirmation")
    assert not env_dir.exists()


@pytest.mark.e2e
def test_can_cancel(env_name, composer_image_version, valid_project_id):
    env_dir = pathlib.Path("composer") / env_name
    run_app(
        f"create --from-image-version {composer_image_version} "
        f"-p {valid_project_id} {env_name}"
    )
    assert env_dir.exists()
    run_app(f"remove {env_name}", input="N", exit_code=1)
    assert env_dir.exists()


@pytest.mark.e2e
def test_remove_two_envs_selected_none(
    composer_image_version, valid_project_id
):
    envs = ["env1", "env2"]
    for env in envs:
        run_app(
            f"create --from-image-version {composer_image_version} "
            f"-p {valid_project_id} {env}"
        )
    env_names = "\n    ".join(envs)
    exp_error = constants.ENVIRONMENT_NOT_SELECTED_ERROR.format(
        env_dir="", env_names=env_names
    )
    exp_error = exp_error[4:]  # skip path
    run_app(f"remove", exit_code=1, expected_output=exp_error)


@pytest.mark.e2e
def test_remove_two_envs_selected_third(
    composer_image_version, valid_project_id
):
    envs = ["env1", "env2"]
    for env in envs:
        run_app(
            f"create --from-image-version {composer_image_version} "
            f"-p {valid_project_id} {env}"
        )
    exp_error = constants.ENVIRONMENT_DIR_NOT_FOUND_ERROR.format(
        env_dir="", create_help=""
    )
    exp_error = exp_error[4:]  # skip path
    run_app("remove env3", exit_code=1, expected_output=exp_error)


@pytest.mark.e2e
def test_remove_no_envs():
    exp_error = constants.ENVIRONMENT_DIR_NOT_FOUND_ERROR.format(
        env_dir="", create_help=""
    )
    exp_error = exp_error[4:]  # skip path
    run_app("remove", exit_code=1, expected_output=exp_error)


@pytest.mark.e2e
def test_without_force_flag(composer_image_version, env_name, valid_project_id):
    env_dir = pathlib.Path("composer") / env_name
    run_app(
        f"create --from-image-version {composer_image_version} "
        f"-p {valid_project_id} --port 9451 {env_name}"
    )
    run_app(f"start {env_name}")
    assert env_dir.exists()
    exp_error = constants.USE_FORCE_TO_REMOVE_ERROR
    run_app(
        f"remove {env_name}", input="y", exit_code=2, expected_output=exp_error
    )
    assert env_dir.exists()


@pytest.mark.e2e
def test_with_force_flag(env_name, composer_image_version, valid_project_id):
    env_dir = pathlib.Path("composer") / env_name
    run_app(
        f"create --from-image-version {composer_image_version} "
        f"-p {valid_project_id} --port 9451 {env_name}"
    )
    run_app(f"start {env_name}")
    assert env_dir.exists()
    run_app(f"remove {env_name}", input="y", exit_code=2)  # no force flag
    assert env_dir.exists()


@pytest.mark.e2e
def test_remove_invalid(env_name, composer_image_version, valid_project_id):
    env_dir = pathlib.Path("composer") / env_name
    run_app(
        f"create --from-image-version {composer_image_version} "
        f"-p {valid_project_id} --port 9451 {env_name}"
    )
    assert env_dir.exists()
    with open(env_dir / "config.json", "w") as fp:
        fp.write("invalid data")
    remove_manually_hint = constants.MALFORMED_CONFIG_REMOVING_CONTAINER
    run_app(
        f"remove {env_name}", input="y", expected_output=remove_manually_hint
    )
    assert not env_dir.exists()
