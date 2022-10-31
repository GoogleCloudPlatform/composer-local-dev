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
import contextlib
import os
import pathlib
from typing import Optional
from unittest import mock

import pytest
from click.testing import CliRunner

from composer_local_dev import cli, constants, utils

TEST_DATA_DIR = pathlib.Path(__file__).parent.parent / "test_data"


@contextlib.contextmanager
def working_directory(path):
    """Changes working directory and returns to previous on exit"""
    prev_cwd = pathlib.Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)


def run_composer_and_assert_exit_code(
    cmd: str, exit_code: int = 0, run_dir: Optional[pathlib.Path] = None
):
    cmd = cmd.split()
    runner = CliRunner()
    if run_dir:
        with working_directory(run_dir):
            result = runner.invoke(cli.cli, cmd)
    else:
        with runner.isolated_filesystem():
            result = runner.invoke(cli.cli, cmd)
    assert result.exit_code == exit_code
    return result


def reformat_cli_output(output):
    reformatted = output.replace("│", "").replace("\n", "")
    reformatted = " ".join(reformatted.split())  # repeated spaces
    return reformatted


def test_create_missing_version_source():
    result = run_composer_and_assert_exit_code(
        "create -p 123 --dags-path . test", exit_code=2
    )
    # rich_click prettify errors and we need to remove extra formatting
    reformated_error = reformat_cli_output(result.output)
    assert (
        "Missing source of the environment. "
        "Provide either --from-source-environment or --from-image-version option."
        in reformated_error
    )


def test_create_both_version_source():
    result = run_composer_and_assert_exit_code(
        "create -p 123 --from-source-environment a --from-image-version b",
        exit_code=2,
    )
    reformated_error = reformat_cli_output(result.output)
    assert (
        "Illegal usage: '--from-source-environment' cannot be used together "
        "with '--from-image-version'" in reformated_error
    )


@mock.patch("composer_local_dev.cli.composer_environment.Environment")
def test_create_no_dags_path(mocked_env):
    run_composer_and_assert_exit_code(
        f"create --project 123 --from-image-version composer-2.0.16-airflow-2.2.5 test",
        exit_code=0,
    )
    _, env_kwargs = mocked_env.call_args
    exp_dags_path = None
    assert exp_dags_path == env_kwargs.get("dags_path")


class TestCreateCommandProjectId:
    @mock.patch("composer_local_dev.cli.utils.get_project_id", autospec=True)
    @mock.patch(
        "composer_local_dev.cli.composer_environment.Environment", autospec=True
    )
    def test_provide_project_id(self, mocked_env, mocked_get_project):
        project_id = "provided-project-id"
        run_composer_and_assert_exit_code(
            f"create --project {project_id} --from-source-environment a --dags-path . test",
            exit_code=0,
        )
        _, env_kwargs = mocked_env.from_source_environment.call_args
        assert project_id == env_kwargs.get("project")
        mocked_get_project.assert_not_called()

    @mock.patch("composer_local_dev.cli.utils.get_project_id", autospec=True)
    @mock.patch(
        "composer_local_dev.cli.composer_environment.Environment", autospec=True
    )
    def test_get_default_project_id_from_cloud(
        self, mocked_env, mocked_get_project
    ):
        project_id = "test123"
        mocked_get_project.return_value = project_id
        run_composer_and_assert_exit_code(
            "create --from-source-environment a --dags-path . test",
            exit_code=0,
        )
        _, env_kwargs = mocked_env.from_source_environment.call_args
        assert project_id == env_kwargs.get("project")

    @mock.patch(
        "subprocess.run", autospec=True, return_value=mock.Mock(stdout="{}")
    )
    @mock.patch(
        "composer_local_dev.cli.composer_environment.Environment", autospec=True
    )
    def test_get_default_project_id_from_cloud_error(
        self, mocked_env, mocked_get_project
    ):
        """Whenever any error happened when trying to retrieve project id"""
        result = run_composer_and_assert_exit_code(
            "create --from-source-environment a --dags-path . test",
            exit_code=2,
        )
        normalized_error = reformat_cli_output(result.output)
        assert (
            "Please provide Google Cloud project id "
            "(using '-p' / '--project' option). Failed to retrieve project id "
            "from gcloud configuration: gcloud configuration is missing "
            "project id." in normalized_error
        )
        mocked_env.assert_not_called()


class TestStartRestartCommand:
    @pytest.fixture
    def mocked_env(self):
        with mock.patch(
            "composer_local_dev.cli.composer_environment.Environment",
            autospec=True,
        ) as mock_env:
            loaded_env = mock.Mock()
            mock_env.load_from_config.return_value = loaded_env
            yield mock_env

    @pytest.fixture()
    def env_path(self):
        return "path"

    @pytest.fixture
    def mocked_resolve_env(self, env_path):
        with mock.patch(
            "composer_local_dev.cli.files.resolve_environment_path",
            return_value=env_path,
        ) as mock_check:
            yield mock_check

    def assert_env_loaded(self, mocked_env, env_path, port=None):
        mocked_env.load_from_config.assert_called_with(env_path, port)

    def assert_run_command(self, command, mocked_env, env_path, port=None):
        run_composer_and_assert_exit_code(
            command,
            exit_code=0,
        )
        self.assert_env_loaded(mocked_env, env_path, port)

    @pytest.mark.parametrize("command", ["start", "restart"])
    def test_start_command(
        self, mocked_env, mocked_resolve_env, env_path, command
    ):
        self.assert_run_command(command, mocked_env, env_path)

    @pytest.mark.parametrize("command", ["start", "restart"])
    def test_start_command_with_port(
        self, mocked_env, mocked_resolve_env, env_path, command
    ):
        port = 8081
        command += f" --port {port}"
        self.assert_run_command(command, mocked_env, env_path, port)

    def test_start_with_invalid_port(
        self, mocked_env, mocked_resolve_env, env_path
    ):
        port = -1
        command = f"start --port {port}"
        result = run_composer_and_assert_exit_code(
            command,
            exit_code=2,
        )
        exp_error = (
            "Invalid value for '--web-server-port' / '--port': "
            "-1 is not in the range"
        )
        assert exp_error in result.output

    @pytest.mark.parametrize("command", ["start", "restart"])
    def test_start_command_with_env(
        self, mocked_env, mocked_resolve_env, env_path, command
    ):
        self.assert_run_command(command, mocked_env, env_path)


class TestStopCommand:
    @mock.patch("composer_local_dev.cli.files.resolve_environment_path")
    @mock.patch(
        "composer_local_dev.cli.composer_environment.Environment", autospec=True
    )
    def test_stop_command(self, mocked_env, mocked_resolve_env):
        env_path = pathlib.Path("path/env_name")
        mock_load_from_config = mock.Mock()
        mocked_env.load_from_config.return_value = mock_load_from_config
        mocked_resolve_env.return_value = env_path
        run_composer_and_assert_exit_code(
            "stop",
            exit_code=0,
        )
        mock_load_from_config.stop.assert_called_once()


class TestListCommand:
    @pytest.mark.parametrize("data_dir", ["missing_composer", "no_envs"])
    def test_list_no_envs(self, data_dir):
        env_dir = (TEST_DATA_DIR / data_dir).resolve()
        result = run_composer_and_assert_exit_code(
            "list", run_dir=env_dir, exit_code=0
        )
        output = reformat_cli_output(result.output)
        assert constants.ENVIRONMENTS_NOT_FOUND.format(path=env_dir) in output

    def test_list_existing_envs(self):
        env_dir = (TEST_DATA_DIR / "two_envs").resolve()
        result = run_composer_and_assert_exit_code(
            "list", run_dir=env_dir, exit_code=0
        )
        output = reformat_cli_output(result.output)
        exp_msg = constants.ENVIRONMENTS_FOUND.format(path=env_dir).replace(
            "\n", ""
        )
        assert exp_msg in output


class TestRunAirflowCmdCommand:
    @mock.patch("composer_local_dev.cli.files.resolve_environment_path")
    @mock.patch(
        "composer_local_dev.cli.composer_environment.Environment", autospec=True
    )
    @pytest.mark.parametrize(
        "command, expected_cmd",
        [("info", ["info"]), ("dags list", ["dags", "list"])],
    )
    def test_run_airflow_command(
        self, mocked_env, mocked_resolve_env, command, expected_cmd
    ):
        env_path = pathlib.Path("path/env_name")
        mock_load_from_config = mock.Mock()
        mocked_env.load_from_config.return_value = mock_load_from_config
        mocked_resolve_env.return_value = env_path
        run_composer_and_assert_exit_code(
            f"run-airflow-cmd env_name {command}",
            exit_code=0,
        )
        mock_load_from_config.run_airflow_command.assert_called_with(
            expected_cmd
        )


class TestDescribeCommand:
    @mock.patch("composer_local_dev.cli.files.resolve_environment_path")
    @mock.patch(
        "composer_local_dev.cli.composer_environment.Environment", autospec=True
    )
    def test_describe(self, mocked_env, mocked_resolve_env):
        env_path = pathlib.Path("path/env_name")
        mock_load_from_config = mock.Mock()
        mocked_env.load_from_config.return_value = mock_load_from_config
        mocked_resolve_env.return_value = env_path
        run_composer_and_assert_exit_code(
            "describe env_name",
            exit_code=0,
        )
        mock_load_from_config.describe.assert_called_once()


class TestLogsCommand:
    @mock.patch("composer_local_dev.cli.files.resolve_environment_path")
    @mock.patch(
        "composer_local_dev.cli.composer_environment.Environment", autospec=True
    )
    def test_logs(self, mocked_env, mocked_resolve_env):
        env_path = pathlib.Path("path/env_name")
        mock_load_from_config = mock.Mock()
        mocked_env.load_from_config.return_value = mock_load_from_config
        mocked_resolve_env.return_value = env_path
        run_composer_and_assert_exit_code(
            "logs --max-lines 10",
            exit_code=0,
        )
        mock_load_from_config.logs.assert_called_once()

    @pytest.mark.parametrize("max_lines", [-10, "abc"])
    def test_invalid_max_lines(self, max_lines):
        expected_error = (
            "Invalid value for '-l' / '--max-lines': "
            f"'{max_lines}' is not a positive integer or 'all' keyword"
        )
        result = run_composer_and_assert_exit_code(
            f"logs --max-lines {max_lines}",
            exit_code=2,
        )
        normalized_error = reformat_cli_output(result.output)
        assert expected_error in normalized_error


def get_image_version_mock(version_id, day, month, year):
    image_version = mock.Mock()
    image_version.image_version_id = version_id
    image_version.release_date = mock.Mock()
    image_version.release_date.day = day
    image_version.release_date.month = month
    image_version.release_date.year = year
    return utils.ImageVersion(image_version)


class TestListAvailableVersionsCommand:
    @mock.patch("composer_local_dev.utils.get_image_versions")
    def test_list_available_versions_no_versions(self, mocked_images):
        mocked_images.return_value = []
        result = run_composer_and_assert_exit_code(
            "list-available-versions --project 123", exit_code=0
        )
        output = reformat_cli_output(result.output)
        assert "Image version" in output

    @mock.patch("composer_local_dev.utils.get_image_versions")
    def test_list_available_versions(self, mocked_images):
        versions = [
            get_image_version_mock("composer-2.0.23-airflow-2.2.5", 1, 1, 2022),
            get_image_version_mock("composer-2.0.23-airflow-2.2.5", 1, 2, 2022),
            get_image_version_mock("composer-2.0.23-airflow-2.2.5", 1, 1, 2023),
            get_image_version_mock("composer-2.0.22-airflow-2.2.5", 1, 1, 2022),
            get_image_version_mock("composer-2.0.23-airflow-2.2.5", 2, 1, 2022),
        ]
        mocked_images.return_value = versions
        result = run_composer_and_assert_exit_code(
            "list-available-versions --project 123", exit_code=0
        )
        output = reformat_cli_output(result.output)
        assert "Image version" in output
