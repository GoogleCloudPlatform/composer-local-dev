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
import shutil
from typing import Optional
from unittest import mock

import pytest
from click.testing import CliRunner

from composer_local_dev import cli


@pytest.fixture()
def image_exists_mock():
    with mock.patch(
        "composer_local_dev.environment.assert_image_exists"
    ) as image_exists_mock:
        yield image_exists_mock


def run_composer_and_assert_exit_code(
    cmd: str, tmp_path: pathlib.Path = None, exit_code: int = 0
):
    cmd = cmd.split()
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        result = runner.invoke(cli.cli, cmd)
        working_dir = pathlib.Path(td)
    assert result.exit_code == exit_code
    return result, working_dir


def assert_environment_directories_exist(
    env_dir: pathlib.Path, dags_path: Optional[pathlib.Path] = None
):
    assert env_dir.exists()
    required_dirs = ["data", "plugins"]
    if dags_path is None:
        required_dirs.append("dags")
    required_files = [
        "airflow.db",
        "config.json",
        "variables.env",
        "requirements.txt",
    ]
    actual_dirs = sorted([p.name for p in env_dir.iterdir() if p.is_dir()])
    actual_files = sorted([p.name for p in env_dir.iterdir() if p.is_file()])
    assert sorted(required_dirs) == actual_dirs
    assert sorted(required_files) == actual_files
    if dags_path is not None:
        assert dags_path.exists()


def test_create_default(image_exists_mock, tmp_path):
    env_name = "fooenv"
    cmd = (
        f"create "
        f"--from-image-version composer-2.0.15-airflow-2.2.5 "
        f"--project 123 "
        f"{env_name}"
    )
    _, work_dir = run_composer_and_assert_exit_code(cmd, tmp_path)
    env_dir = work_dir / "composer" / env_name
    assert_environment_directories_exist(env_dir)
    shutil.rmtree(work_dir)


def test_create_provide_dags_path(image_exists_mock, tmp_path):
    env_name = "fooenv"
    dags_path = tmp_path / "test" / "dags"
    cmd = (
        f"create "
        f"--from-image-version composer-2.0.15-airflow-2.2.5 "
        f"--project 123 "
        f"--dags-path {dags_path} "
        f"{env_name}"
    )
    _, work_dir = run_composer_and_assert_exit_code(cmd, tmp_path)
    env_dir = work_dir / "composer" / env_name
    assert_environment_directories_exist(env_dir, dags_path=dags_path)
    shutil.rmtree(work_dir)
