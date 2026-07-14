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

import json
import os
import pathlib
from unittest import mock

import pytest
from click.testing import CliRunner

from composer_local_dev.cli import cli
from composer_local_dev.environment import Environment


@pytest.mark.e2e
@mock.patch("composer_local_dev.environment.assert_image_exists")
def test_create_environment_with_editable_dependencies(
    mock_assert_image, tmp_path, monkeypatch
):
    # Change current working directory to isolated tmp_path
    monkeypatch.chdir(tmp_path)

    # Create dummy editable package directories
    pkg_dir = tmp_path / "my_local_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        "[build-system]\n"
        "requires = ['flit_core']\n"
        "build-backend = 'flit_core.buildapi'\n"
        "\n"
        "[project]\n"
        "name = 'my_local_pkg'\n"
        "version = '0.1.0'\n"
    )
    (pkg_dir / "my_local_pkg").mkdir()
    (pkg_dir / "my_local_pkg" / "__init__.py").write_text("def test(): pass")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "create",
            "--from-image-version",
            "composer-2.17.6-airflow-2.11.1",
            "--project",
            "local-dev-tool-testing",
            "--editable-dependencies",
            str(pkg_dir),
            "test_env_editable",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"

    config_file_path = (
        tmp_path / "composer" / "test_env_editable" / "config.json"
    )
    assert config_file_path.is_file()

    with open(config_file_path) as f:
        config = json.load(f)

    assert config["editable_dependencies"] == [str(pkg_dir)]

    # Load environment to check default environment variables are set correctly
    env = Environment.load_from_config(
        tmp_path / "composer" / "test_env_editable", None, None
    )
    default_vars = env.get_default_environment_variables({})

    assert "COMPOSER_EDITABLE_DEPENDENCIES" in default_vars
    expected_deps_val = f"/home/airflow/editable_deps/0_my_local_pkg"
    assert default_vars["COMPOSER_EDITABLE_DEPENDENCIES"] == expected_deps_val
