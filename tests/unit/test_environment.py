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
import getpass
import os
import pathlib
import platform
import re
from unittest import mock

import pytest
from docker import errors as docker_errors
from google.api_core import exceptions as api_exception
from google.auth import exceptions as auth_exception

from composer_local_dev import constants, environment, errors

TEST_DATA_DIR = pathlib.Path(__file__).parent.parent / "test_data"


@pytest.fixture
@mock.patch("composer_local_dev.environment.docker.from_env")
@mock.patch("composer_local_dev.environment.files.resolve_dags_path")
def default_env(mocked_docker, mocked_dags, tmp_path):
    env_dir_path = tmp_path / ".compose" / "my_env"
    env = environment.Environment(
        env_dir_path=env_dir_path,
        project_id="",
        image_version="composer-2.0.8-airflow-2.2.3",
        location="location",
        dags_path=str(pathlib.Path("path")),
        dag_dir_list_interval=10,
    )
    return env


@contextlib.contextmanager
def working_directory(path):
    """Changes working directory and returns to previous on exit"""
    prev_cwd = pathlib.Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)


class TestEnvironment:
    @staticmethod
    def compare_envs(expected_env, actual_env):
        expected_env.docker_client = None
        actual_env.docker_client = None
        assert actual_env.__dict__ == expected_env.__dict__

    @mock.patch("composer_local_dev.environment.docker.from_env")
    def test_get_docker_client_error(self, mocked_docker, tmp_path):
        mocked_docker.side_effect = docker_errors.DockerException(
            "Connection aborted"
        )
        airflow_version = "2.2.5"
        composer_version = "2.0.3"
        exp_err = constants.DOCKER_NOT_AVAILABLE_ERROR.format(
            error="Connection aborted"
        )
        image_version = f"composer-{composer_version}-airflow-{airflow_version}"
        dags_path = str(pathlib.Path(tmp_path))
        with pytest.raises(
            errors.DockerNotAvailableError,
            match=exp_err,
        ):
            environment.Environment(
                image_version=image_version,
                project_id="",
                location="location",
                env_dir_path=pathlib.Path("env"),
                port=9000,
                dags_path=dags_path,
            )

    def test_get_docker_image_tag_from_image_version(self):
        image_version = "composer-2.0.8-airflow-2.2.3"
        expected_image = (
            "us-docker.pkg.dev/cloud-airflow-releaser/"
            "airflow-worker-scheduler-2-2-3/airflow-worker-scheduler-2-2-3:"
            "composer-2.0.8-airflow-2-2-3"
        )
        parsed_image = environment.get_docker_image_tag_from_image_version(
            image_version
        )
        assert expected_image == parsed_image

    @mock.patch("composer_local_dev.environment.artifactregistry_v1")
    def test_assert_image_exists_not_found(self, mocked_artifact):
        mock_client = mock.Mock()
        mock_client.get_tag.side_effect = api_exception.NotFound("")
        mocked_artifact.ArtifactRegistryClient.return_value = mock_client
        image_version = "composer-1.0.0-airflow-2.2.0"
        image_tag = "composer-1.0.0-airflow-2-2-0"
        with pytest.raises(
            errors.ImageNotFoundError,
            match=re.escape(
                constants.IMAGE_TAG_DOES_NOT_EXIST_ERROR.format(
                    image_tag=image_tag
                )
            ),
        ):
            environment.assert_image_exists(image_version)

    @mock.patch("composer_local_dev.environment.artifactregistry_v1")
    def test_assert_image_exists_permission_denied(self, mocked_artifact):
        mock_client = mock.Mock()
        mock_client.get_tag.side_effect = api_exception.PermissionDenied("")
        mocked_artifact.ArtifactRegistryClient.return_value = mock_client
        image_version = "composer-1.0.0-airflow-2.2.0"
        image_tag = "composer-1.0.0-airflow-2-2-0"
        warning = (
            f"Received permission denied when checking image existence "
            f"for {image_tag}"
        )
        with pytest.warns(UserWarning, match=warning):
            environment.assert_image_exists(image_version)

    @mock.patch("composer_local_dev.environment.artifactregistry_v1")
    def test_assert_image_exists_auth_error(self, mocked_artifact):
        mock_client = mock.Mock()
        error_msg = "Test error"
        exp_error = constants.AUTH_INVALID_ERROR.format(error=error_msg)
        mock_client.get_tag.side_effect = (
            auth_exception.DefaultCredentialsError(error_msg)
        )
        mocked_artifact.ArtifactRegistryClient.return_value = mock_client
        image_version = "composer-1.0.0-airflow-2.2.0"
        with pytest.raises(
            errors.InvalidAuthError,
            match=re.escape(exp_error),
        ):
            environment.assert_image_exists(image_version)

    @mock.patch("composer_local_dev.environment.docker.from_env")
    @mock.patch("composer_local_dev.environment.files.resolve_dags_path")
    @mock.patch(
        "composer_local_dev.environment.get_software_config_from_environment"
    )
    def test_from_source_with_empty_pypi_packages(
        self, mocked_fn, mocked_dags, mocked_docker
    ):
        image_version = "composer-2.0.8-airflow-2.2.3"
        mocked_sw = mock.Mock()
        mocked_sw.pypi_packages = {}
        mocked_sw.airflow_config_overrides = {}
        mocked_sw.env_variables = {}
        mocked_sw.image_version = "composer-2.0.8-airflow-2.2.3"
        mocked_fn.return_value = mocked_sw
        env = environment.Environment.from_source_environment(
            "test123",
            "project",
            "us-central1",
            pathlib.Path("composer", "env_dir"),
            8082,
            str(pathlib.Path("dags")),
        )
        expected_env = environment.Environment(
            env_dir_path=pathlib.Path("composer", "env_dir"),
            project_id="project",
            image_version=image_version,
            location="us-central1",
            dags_path=str(pathlib.Path("dags")),
            dag_dir_list_interval=10,
            port=8082,
        )
        self.compare_envs(expected_env, env)

    @mock.patch("composer_local_dev.environment.docker.from_env")
    @mock.patch("composer_local_dev.environment.files.resolve_dags_path")
    @mock.patch(
        "composer_local_dev.environment.get_docker_image_tag_from_image_version"
    )
    @mock.patch(
        "composer_local_dev.environment.get_software_config_from_environment"
    )
    def test_from_source_with_pypi_packages(
        self, mocked_sw_config, mocked_parse_image, mocked_dags, mocked_docker
    ):
        image_version = "composer-2.0.8-airflow-2.2.3"
        packages = {
            "requests": "",
            "black": "==21.0",
            "flake": "[toml]",
        }
        mocked_sw = mock.Mock()
        mocked_sw.pypi_packages = packages
        mocked_sw.airflow_config_overrides = {}
        mocked_sw.env_variables = {}
        mocked_sw.image_version = image_version
        mocked_sw_config.return_value = mocked_sw

        env = environment.Environment.from_source_environment(
            "env_name",
            "project_with_packages",
            "eu-west",
            pathlib.Path("composer", "env_name"),
            None,
            str(pathlib.Path("dags", "folder")),
        )
        expected_env = environment.Environment(
            env_dir_path=pathlib.Path("composer", "env_name"),
            project_id="project_with_packages",
            image_version=image_version,
            location="eu-west",
            dags_path=str(pathlib.Path("dags", "folder")),
            dag_dir_list_interval=10,
            port=8080,
            pypi_packages=packages,
        )
        self.compare_envs(expected_env, env)

    @mock.patch("composer_local_dev.environment.docker.from_env")
    @mock.patch("composer_local_dev.environment.files.resolve_dags_path")
    @mock.patch(
        "composer_local_dev.environment.get_docker_image_tag_from_image_version"
    )
    @mock.patch(
        "composer_local_dev.environment.get_software_config_from_environment"
    )
    def test_from_source_with_env_variables(
        self, mocked_sw_config, mocked_parse_image, mocked_dags, mocked_docker
    ):
        image_version = "composer-2.0.8-airflow-2.2.3"
        airflow_overrides_from_api = {
            "section-key": "VALUE",
            "section-key2": "VALUE",
        }
        env_variables_from_api = {
            "ENV_VARIABLE": "VALUE",
            "OTHER_variable": "123",
        }
        env_variables_parsed = {
            "AIRFLOW__SECTION__KEY": "VALUE",
            "AIRFLOW__SECTION__KEY2": "VALUE",
            "ENV_VARIABLE": "",
            "OTHER_variable": "",
        }
        mocked_sw = mock.Mock()
        mocked_sw.pypi_packages = {}
        mocked_sw.airflow_config_overrides = airflow_overrides_from_api
        mocked_sw.env_variables = env_variables_from_api
        mocked_sw.image_version = image_version
        mocked_sw_config.return_value = mocked_sw

        env = environment.Environment.from_source_environment(
            "env_name",
            "project_with_packages",
            "eu-west",
            pathlib.Path("composer", "env_name"),
            None,
            pathlib.Path("dags", "folder"),
        )
        expected_env = environment.Environment(
            env_dir_path=pathlib.Path("composer", "env_name"),
            project_id="project_with_packages",
            image_version=image_version,
            location="eu-west",
            dags_path=str(pathlib.Path("dags", "folder")),
            dag_dir_list_interval=10,
            port=8080,
            pypi_packages={},
            environment_vars=env_variables_parsed,
        )
        self.compare_envs(expected_env, env)

    @mock.patch("composer_local_dev.environment.docker.from_env")
    @mock.patch("composer_local_dev.environment.files.resolve_dags_path")
    @mock.patch(
        "composer_local_dev.environment.get_docker_image_tag_from_image_version"
    )
    @mock.patch(
        "composer_local_dev.environment.get_software_config_from_environment"
    )
    def test_from_source_with_block_listed_env_vars(
        self, mocked_sw_config, mocked_parse_image, mocked_dags, mocked_docker
    ):
        image_version = "composer-2.0.8-airflow-2.2.3"
        airflow_overrides_from_api = {
            "section-key": "VALUE",
            "core-executor": "Kubernetes",
        }
        env_variables_from_api = {
            "ENV_VARIABLE": "VALUE",
            "AIRFLOW_HOME": "123",
        }
        env_variables_parsed = {
            "AIRFLOW__SECTION__KEY": "VALUE",
            "ENV_VARIABLE": "",
        }
        mocked_sw = mock.Mock()
        mocked_sw.pypi_packages = {}
        mocked_sw.airflow_config_overrides = airflow_overrides_from_api
        mocked_sw.env_variables = env_variables_from_api
        mocked_sw.image_version = image_version
        mocked_sw_config.return_value = mocked_sw

        env = environment.Environment.from_source_environment(
            "env_name",
            "project_with_packages",
            "eu-west",
            pathlib.Path("composer", "env_name"),
            None,
            pathlib.Path("dags", "folder"),
        )
        expected_env = environment.Environment(
            env_dir_path=pathlib.Path("composer", "env_name"),
            project_id="project_with_packages",
            image_version=image_version,
            location="eu-west",
            dags_path=str(pathlib.Path("dags", "folder")),
            dag_dir_list_interval=10,
            port=8080,
            pypi_packages={},
            environment_vars=env_variables_parsed,
        )
        self.compare_envs(expected_env, env)

    @mock.patch("composer_local_dev.environment.docker.from_env")
    @pytest.mark.parametrize(
        "composer_version, airflow_version",
        [
            (
                "2.0.3",
                "2.2.3",
            ),
            (
                "1.10.0",
                "3.0.0",
            ),
        ],
    )
    def test_from_image(
        self, mocked_docker, composer_version, airflow_version, tmp_path
    ):
        image_version = f"composer-{composer_version}-airflow-{airflow_version}"
        dags_path = str(pathlib.Path(tmp_path))
        env = environment.Environment(
            image_version=image_version,
            project_id="",
            location="location",
            env_dir_path=pathlib.Path("env"),
            port=9000,
            dags_path=dags_path,
        )
        expected_env = environment.Environment(
            env_dir_path=pathlib.Path("env"),
            project_id="",
            image_version=image_version,
            location="location",
            dags_path=dags_path,
            dag_dir_list_interval=10,
            port=9000,
            pypi_packages={},
        )
        self.compare_envs(expected_env, env)

    @pytest.mark.parametrize(
        "pypi_packages",
        [
            {
                "requests": "",
                "black": "==21.0",
                "flake": "[toml]",
            },
            {},
        ],
    )
    @pytest.mark.parametrize("port", [None, 8090])
    @mock.patch("composer_local_dev.environment.docker.from_env")
    @mock.patch("composer_local_dev.environment.assert_image_exists")
    def test_create_and_load_from_config(
        self, mocked_docker, mocked_assert, pypi_packages, port, tmp_path
    ):
        env_dir_path = tmp_path / ".compose" / "my_env"
        image_version = "composer-2.0.8-airflow-2.2.3"
        expected_env = environment.Environment(
            env_dir_path=env_dir_path,
            project_id="",
            image_version=image_version,
            location="location",
            dags_path=str(pathlib.Path(tmp_path)),
            dag_dir_list_interval=10,
            port=port,
            pypi_packages=pypi_packages,
        )
        expected_env.create()

        env = environment.Environment.load_from_config(env_dir_path, port)
        env.pypi_packages = (
            pypi_packages  # load_from_config does not load pypi packages
        )
        self.compare_envs(expected_env, env)

    def test_missing_variables_env(self):
        env_dir = (TEST_DATA_DIR / "missing_composer").resolve()
        exp_error = (
            f"Environment variables file '{env_dir / 'variables.env'}' "
            f"not found."
        )
        with pytest.raises(errors.ComposerCliError) as err:
            environment.load_environment_variables(env_dir)
            assert str(err) == exp_error

    def test_load_environment_variables_filter_blocked_env_vars(self):
        env_dir = (TEST_DATA_DIR / "blocked_env_vars").resolve()
        expected_env_vars = {"RANDOM_NAME": "123"}
        env_vars = environment.load_environment_variables(env_dir)
        assert expected_env_vars == env_vars

    def test_load_environment_variables_commented(self):
        env_dir = (TEST_DATA_DIR / "commented_env_vars").resolve()
        expected_env_vars = {"ONLY_NAME": "abc"}
        env_vars = environment.load_environment_variables(env_dir)
        assert expected_env_vars == env_vars

    @mock.patch("composer_local_dev.environment.docker.from_env")
    @mock.patch("composer_local_dev.environment.assert_image_exists")
    def test_environment_vars_to_env_file(
        self, mocked_docker, mock_assert_image, tmp_path
    ):
        environment_vars = {
            "AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG": "",
            "MY_VALUE": "1",
        }
        env_dir_path = tmp_path / ".compose" / "my_env"
        env_dir_path.mkdir(parents=True)
        image_version = "composer-2.0.8-airflow-2.2.3"
        env = environment.Environment(
            env_dir_path=env_dir_path,
            project_id="",
            image_version=image_version,
            location="location",
            dags_path=str(pathlib.Path(tmp_path)),
            dag_dir_list_interval=10,
            environment_vars=environment_vars,
        )
        env.environment_vars_to_env_file()
        expected_vars = [
            "# AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG=",
            "# MY_VALUE=",
        ]
        actual_vars = []
        with open(env_dir_path / "variables.env") as fp:
            for line in fp:
                actual_vars.append(line.strip())
        assert actual_vars == expected_vars

    def test_invalid_env_variables(self):
        env_dir = (TEST_DATA_DIR / "invalid_variables").resolve()
        env_file_path = str(env_dir / "variables.env")
        exp_error = constants.INVALID_ENV_VARIABLES_FILE_ERROR.format(
            env_file_path=env_file_path, line="AIRFLOW_KEYVALUE"
        )
        with pytest.raises(errors.FailedToParseVariablesError) as err:
            environment.load_environment_variables(env_dir)
            assert str(err) == exp_error

    @mock.patch("composer_local_dev.environment.docker.from_env")
    @mock.patch(
        "composer_local_dev.environment.get_docker_image_tag_from_image_version"
    )
    def test_missing_requirements(self, mocked_docker, mocked_tag, tmpdir):
        env_dir = pathlib.Path(tmpdir)
        requirement_file = str(env_dir / "requirements.txt")
        env = environment.Environment(
            env_dir_path=env_dir,
            project_id="",
            image_version="",
            location="location",
            dags_path=str(env_dir),
        )
        exp_error = f"Missing '{requirement_file}' file."
        with pytest.raises(errors.ComposerCliError) as err:
            env.assert_requirements_exist()
            assert str(err) == exp_error

    @mock.patch("composer_local_dev.environment.docker.from_env")
    def test_get_container(self, mocked_docker, default_env):
        container = mock.Mock()
        default_env.docker_client.containers.get = mock.Mock(
            return_value=container
        )
        actual_container = default_env.get_container()
        assert actual_container == container

    @mock.patch("composer_local_dev.environment.docker.from_env")
    def test_get_container_assert_running_passing(
        self, mocked_docker, default_env
    ):
        container = mock.Mock()
        container.status = constants.ContainerStatus.RUNNING
        default_env.docker_client.containers.get = mock.Mock(
            return_value=container
        )
        actual_container = default_env.get_container(assert_running=True)
        assert actual_container == container

    @mock.patch("composer_local_dev.environment.docker.from_env")
    def test_get_container_assert_running_failing(
        self, mocked_docker, default_env
    ):
        container = mock.Mock()
        container.status = "other_status"
        default_env.docker_client.containers.get = mock.Mock(
            return_value=container
        )
        with pytest.raises(
            errors.EnvironmentNotRunningError, match=constants.ENV_NOT_RUNNING
        ):
            default_env.get_container(assert_running=True)

    @mock.patch("composer_local_dev.environment.docker.from_env")
    def test_get_container_not_started(self, mocked_docker, default_env):
        default_env.docker_client.containers.get.side_effect = (
            docker_errors.NotFound("")
        )
        with pytest.raises(
            errors.ComposerCliError,
            match=constants.ENV_NOT_RUNNING,
        ):
            default_env.get_container()

    @mock.patch("composer_local_dev.environment.docker.from_env")
    def test_get_container_any_error(self, mocked_docker, default_env):
        default_env.docker_client.containers.get.side_effect = ValueError(
            "Mocked error"
        )
        with pytest.raises(
            ValueError,
            match="Mocked error",
        ):
            default_env.get_container()

    @mock.patch("composer_local_dev.environment.get_image_mounts")
    def test_create_docker_container(self, mocked_mounts, default_env):
        default_env.create_docker_container()
        ports = {
            f"8080/tcp": default_env.port,
        }
        environment = {
            "AIRFLOW__API__AUTH_BACKEND": "airflow.api.auth.backend.default",
            "AIRFLOW__WEBSERVER__EXPOSE_CONFIG": "true",
            "AIRFLOW__CORE__LOAD_EXAMPLES": "false",
            "AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL": default_env.dag_dir_list_interval,
            "AIRFLOW__CORE__DAGS_FOLDER": "/home/airflow/gcs/dags",
            "AIRFLOW__CORE__PLUGINS_FOLDER": "/home/airflow/gcs/plugins",
            "AIRFLOW__CORE__DATA_FOLDER": "/home/airflow/gcs/data",
            "AIRFLOW__WEBSERVER__RELOAD_ON_PLUGIN_CHANGE": "True",
            "COMPOSER_PYTHON_VERSION": "3",
            "COMPOSER_CONTAINER_RUN_AS_HOST_USER": "False",
            "COMPOSER_HOST_USER_NAME": f"{getpass.getuser()}",
            "COMPOSER_HOST_USER_ID": f"{os.getuid() if platform.system() != 'Windows' else ''}",
            "AIRFLOW_HOME": "/home/airflow/airflow",
            "AIRFLOW_CONN_GOOGLE_CLOUD_DEFAULT": f"google-cloud-platform://?"
            f"extra__google_cloud_platform__project={default_env.project_id}&"
            f"extra__google_cloud_platform__scope="
            f"https://www.googleapis.com/auth/cloud-platform",
        }
        default_env.docker_client.containers.create.assert_called_with(
            default_env.image_tag,
            name="composer-local-dev-my_env",
            entrypoint="sh /home/airflow/entrypoint.sh",
            environment=environment,
            mounts=mocked_mounts(),
            ports=ports,
            mem_limit=constants.DOCKER_CONTAINER_MEMORY_LIMIT,
            detach=True,
        )

    @pytest.mark.parametrize(
        "container_exists, create_container", [(False, True), (True, False)]
    )
    @mock.patch("composer_local_dev.files.assert_dag_path_exists")
    @mock.patch("composer_local_dev.environment.assert_image_exists")
    @mock.patch("composer_local_dev.environment.files.create_empty_file")
    @mock.patch("composer_local_dev.environment.files.fix_file_permissions")
    @mock.patch("composer_local_dev.environment.files.fix_line_endings")
    def test_start_container(
        self,
        mocked_assert,
        mocked_dag_assert,
        mocked_create,
        mocked_fix,
        mocked_line_fix,
        container_exists,
        create_container,
        default_env,
    ):
        default_env.assert_requirements_exist = mock.Mock()
        default_env.get_container = mock.Mock()
        if not container_exists:
            default_env.get_container.side_effect = (
                errors.EnvironmentNotRunningError()
            )
        default_env.create_docker_container = mock.Mock()
        default_env.wait_for_start = mock.Mock()
        default_env.start()
        default_env.assert_requirements_exist.assert_called_once()
        # do not create container if it exists
        assert default_env.create_docker_container.call_count == int(
            create_container
        )
        default_env.wait_for_start.assert_called_once()

    @mock.patch("composer_local_dev.files.assert_dag_path_exists")
    @mock.patch("composer_local_dev.environment.assert_image_exists")
    @mock.patch("composer_local_dev.environment.files.create_empty_file")
    @mock.patch("composer_local_dev.environment.files.fix_file_permissions")
    @mock.patch("composer_local_dev.environment.files.fix_line_endings")
    def test_start_already_running(
        self,
        mocked_assert,
        mocked_dag_assert,
        mocked_create,
        mocked_fix,
        mocked_line_endings,
        default_env,
    ):
        default_env.assert_requirements_exist = mock.Mock()
        default_env.wait_for_start = mock.Mock()
        container = mock.Mock()
        container.status = "running"
        default_env.get_container = mock.Mock(return_value=container)
        exp_error = constants.ENVIRONMENT_ALREADY_RUNNING.format(name="my_env")
        with pytest.raises(
            errors.EnvironmentAlreadyRunningError, match=exp_error
        ):
            default_env.start()

    @mock.patch("composer_local_dev.files.assert_dag_path_exists")
    @mock.patch("composer_local_dev.environment.assert_image_exists")
    @mock.patch("composer_local_dev.environment.files.create_empty_file")
    @mock.patch("composer_local_dev.environment.files.fix_file_permissions")
    @mock.patch("composer_local_dev.environment.files.fix_line_endings")
    def test_restart_already_running(
        self,
        mocked_assert,
        mocked_dag_assert,
        mocked_create,
        mocked_fix,
        mocked_line_endings,
        default_env,
    ):
        default_env.assert_requirements_exist = mock.Mock()
        default_env.wait_for_start = mock.Mock()
        container = mock.Mock()
        container.status = "running"
        default_env.get_container = mock.Mock(return_value=container)
        exp_error = constants.ENVIRONMENT_ALREADY_RUNNING.format(name="my_env")
        default_env.restart()

    def test_describe_started(self, default_env):
        env_state = "running"
        default_env.status = mock.Mock(return_value=env_state)
        default_env.prepare_env_description = mock.Mock()
        default_env.describe()
        default_env.prepare_env_description.assert_called_with(env_state)

    @mock.patch("composer_local_dev.utils.resolve_gcloud_config_path")
    def test_prepare_env_description_running(self, mocked_gcloud, default_env):
        env_state = "running"
        formatted_state = "[bold green]running[/]"
        port = 8081
        mocked_gcloud.return_value = "path"
        web_url = constants.WEBSERVER_URL_MESSAGE.format(port=port)
        exp_desc = constants.DESCRIBE_ENV_MESSAGE.format(
            name=default_env.name,
            state=formatted_state,
            web_url=web_url,
            image_version=default_env.image_version,
            dags_path=default_env.dags_path,
            gcloud_path="path",
        )
        default_env.get_host_port = mock.Mock(return_value=port)
        description = default_env.prepare_env_description(env_state)
        assert exp_desc == description

    @mock.patch("composer_local_dev.utils.resolve_gcloud_config_path")
    def test_prepare_env_description_not_running(
        self, mocked_gcloud, default_env
    ):
        env_state = "exited"
        formatted_state = "[bold red]exited[/]"
        port = 8081
        mocked_gcloud.return_value = "path"
        web_url = ""
        exp_desc = constants.DESCRIBE_ENV_MESSAGE.format(
            name=default_env.name,
            state=formatted_state,
            web_url=web_url,
            image_version=default_env.image_version,
            dags_path=default_env.dags_path,
            gcloud_path="path",
        )
        default_env.get_host_port = mock.Mock(return_value=port)
        description = default_env.prepare_env_description(env_state)
        assert exp_desc == description

    def test_create_docker_container_duplicate(self, default_env):
        default_env.get_image_mounts = mock.Mock()
        mocked_response = mock.Mock()
        mocked_response.status_code = constants.CONFLICT_ERROR_CODE
        default_env.docker_client.containers.create = mock.Mock(
            side_effect=docker_errors.APIError("", response=mocked_response)
        )

        with pytest.raises(
            errors.ComposerCliError,
            match="Composer local development for environment 'my_env' "
            "is already running. "
            "Stop or restart it if you want to run it.",
        ):
            default_env.create_docker_container()

    def test_create_docker_container_mount_permission(self, default_env):
        default_env.get_image_mounts = mock.Mock()
        mocked_response = mock.Mock()
        mocked_response.status_code = 400
        error = (
            'Bad Request ("invalid mount config for type "bind": '
            "bind source path does not exist"
        )
        default_env.docker_client.containers.create = mock.Mock(
            side_effect=docker_errors.APIError(
                "", explanation=error, response=mocked_response
            )
        )

        with pytest.raises(errors.EnvironmentStartError) as err:
            default_env.create_docker_container()
        assert (
            constants.DOCKER_PERMISSION_ERROR_HINT.format(
                docs_faq_url=constants.COMPOSER_FAQ_MOUNTING_LINK
            )
            in err.value.message
        )

    def test_create_docker_container_pull_not_existing_image(self, default_env):
        default_env.get_image_mounts = mock.Mock()
        response_mock = mock.Mock()
        response_mock.status_code = 450
        side_effect = [
            docker_errors.ImageNotFound("", response=response_mock),
            mock.DEFAULT,
        ]
        default_env.docker_client.containers.create = mock.Mock(
            side_effect=side_effect
        )
        default_env.pull_image = mock.Mock()
        default_env.create_docker_container()
        default_env.pull_image.assert_called_once()

    @mock.patch("composer_local_dev.files.assert_dag_path_exists")
    @mock.patch("composer_local_dev.environment.assert_image_exists")
    @mock.patch("composer_local_dev.environment.files.create_empty_file")
    @mock.patch("composer_local_dev.environment.files.fix_file_permissions")
    @mock.patch("composer_local_dev.environment.files.fix_line_endings")
    def test_start_used_port(
        self,
        mocked_assert,
        mocked_dag_assert,
        mocked_create,
        mocked_fix,
        mocked_line_fix,
        default_env,
    ):
        default_env.port = 8083
        default_env.assert_requirements_exist = mock.Mock()
        container = mock.Mock()
        mocked_response = mock.Mock()
        mocked_response.status_code = constants.SERVER_ERROR_CODE
        mocked_response.reason = (
            "Bind for 0.0.0.0:8080 failed: port is already allocated"
        )
        container.start.side_effect = docker_errors.APIError(
            "", response=mocked_response
        )
        default_env.get_or_create_container = mock.Mock(return_value=container)
        with pytest.raises(
            errors.ComposerCliError,
            match=constants.PORT_IN_USE_ERROR.format(port=8083),
        ):
            default_env.start()

    @pytest.mark.parametrize("remove_container", [True, False])
    def test_stop_container(self, remove_container, default_env):
        container = mock.Mock()
        default_env.get_container = mock.Mock(return_value=container)
        default_env.stop(remove_container=remove_container)
        container.stop.assert_called_once()
        assert container.remove.call_count == int(remove_container)


def get_container_logs_mock(log_lines, status="running"):
    container = mock.Mock()
    container.status = status
    container.logs = mock.Mock(return_value=log_lines)
    return mock.Mock(return_value=container)


class TestWaitForStart:
    @mock.patch(
        "composer_local_dev.environment.time.time",
        side_effect=[1, 1 + constants.OPERATION_TIMEOUT_SECONDS],
    )
    def test_wait_for_start_timeout(self, mocked_time, default_env):
        container = mock.Mock()
        container.status = "running"
        container.logs = mock.Mock(return_value=[b"Log lines"])
        default_env.get_container = mock.Mock(return_value=container)
        with pytest.raises(
            errors.ComposerCliError,
            match=f"Environment did not start in {constants.OPERATION_TIMEOUT_SECONDS} seconds.",
        ):
            default_env.wait_for_start()

    def test_wait_for_start_failed(self, default_env):
        default_env.get_container = get_container_logs_mock([], "not_running")
        with pytest.raises(
            errors.EnvironmentStartError,
            match=constants.ENVIRONMENT_FAILED_TO_START_ERROR,
        ):
            default_env.wait_for_start()

    def test_wait_for_start(self, default_env):
        log_lines = [b"Log lines"] * 10 + [b"Searching for files in path..."]
        default_env.get_container = get_container_logs_mock(log_lines)
        default_env.wait_for_start()

    def test_get_host_port(self, default_env):
        exp_port = 1234
        container_mock = mock.Mock()
        container_mock.ports = {"8080/tcp": [{"HostPort": exp_port}]}
        default_env.get_container = mock.Mock(return_value=container_mock)
        port = default_env.get_host_port()
        assert exp_port == port

    def test_get_host_port_invalid(self, default_env):
        exp_port = 1235
        container_mock = mock.Mock()
        container_mock.ports = {"8080/tcp": []}
        default_env.get_container = mock.Mock(return_value=container_mock)
        default_env.port = exp_port
        port = default_env.get_host_port()
        assert exp_port == port


class TestLogs:
    BINARY_LOG_LINE = b"Log lines\nwith multiline\n"
    BINARY_LOG_LINE_LIST = [b"Log lines", b"with multiline"]
    EXPECTED_LINES = "Log lines\nwith multiline\n\n"
    EXPECTED_LINES_FOR_FOLLOW = "Log lines\nwith multiline\n"
    TEST_10_LINES_FOLLOW = (
        10,
        True,
        BINARY_LOG_LINE_LIST,
        EXPECTED_LINES_FOR_FOLLOW,
    )
    TEST_10_LINES_NOT_FOLLOW = (10, False, BINARY_LOG_LINE, EXPECTED_LINES)
    TEST_ALL_LINES_FOLLOW = (
        "all",
        True,
        BINARY_LOG_LINE_LIST,
        EXPECTED_LINES_FOR_FOLLOW,
    )
    TEST_ALL_LINES_NOT_FOLLOW = ("all", False, BINARY_LOG_LINE, EXPECTED_LINES)

    @pytest.mark.parametrize(
        "max_lines,follow,log_lines,expected_lines",
        [
            TEST_10_LINES_FOLLOW,
            TEST_10_LINES_NOT_FOLLOW,
            TEST_ALL_LINES_FOLLOW,
            TEST_ALL_LINES_NOT_FOLLOW,
        ],
    )
    def test_get_10_lines_follow(
        self, default_env, max_lines, follow, log_lines, expected_lines, capsys
    ):
        log_lines = [b"Log lines", b"with multiline"]
        expected_lines = "Log lines\nwith multiline\n"
        default_env.get_container = get_container_logs_mock(log_lines)
        default_env.logs(max_lines=10, follow=True)
        captured = capsys.readouterr()
        assert expected_lines == captured.out

    def test_container_not_running(self, default_env):
        default_env.docker_client.containers.get.side_effect = (
            docker_errors.NotFound("")
        )
        with pytest.raises(
            errors.EnvironmentNotRunningError,
            match=constants.ENV_NOT_RUNNING,
        ):
            default_env.logs(10, False)


def test_get_environment_variables():
    project_id = "123"
    dag_interval = 105
    extra_vars = {"VAR_1": "123", "VAR_2": "a"}
    expected_vars = {
        "AIRFLOW__API__AUTH_BACKEND": "airflow.api.auth.backend.default",
        "AIRFLOW__WEBSERVER__EXPOSE_CONFIG": "true",
        "AIRFLOW__CORE__LOAD_EXAMPLES": "false",
        "AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL": 105,
        "AIRFLOW__CORE__DAGS_FOLDER": "/home/airflow/gcs/dags",
        "AIRFLOW__CORE__PLUGINS_FOLDER": "/home/airflow/gcs/plugins",
        "AIRFLOW__CORE__DATA_FOLDER": "/home/airflow/gcs/data",
        "AIRFLOW__WEBSERVER__RELOAD_ON_PLUGIN_CHANGE": "True",
        "COMPOSER_PYTHON_VERSION": "3",
        "AIRFLOW_HOME": "/home/airflow/airflow",
        "COMPOSER_CONTAINER_RUN_AS_HOST_USER": "False",
        "COMPOSER_HOST_USER_NAME": f"{getpass.getuser()}",
        "COMPOSER_HOST_USER_ID": f"{os.getuid() if platform.system() != 'Windows' else ''}",
        "AIRFLOW_CONN_GOOGLE_CLOUD_DEFAULT": "google-cloud-platform://?"
        "extra__google_cloud_platform__project=123&"
        "extra__google_cloud_platform__scope="
        "https://www.googleapis.com/auth/cloud-platform",
        **extra_vars,
    }
    default_vars = environment.get_default_environment_variables(
        dag_interval, project_id
    )
    actual_vars = {**default_vars, **extra_vars}
    assert expected_vars == actual_vars


@mock.patch("composer_local_dev.environment.docker.types.Mount", autospec=True)
def test_get_image_mounts(mocked_mount):
    path = pathlib.Path("path/dir")
    dags_path = "path/to/dags"
    gcloud_path = "config/path"
    requirements = path / "requirements.txt"
    airflow_db_path = path / "airflow.db"
    expected_mounts = [
        mock.call(
            source=str(requirements),
            target="/home/airflow/composer_requirements.txt",
            type="bind",
        ),
        mock.call(
            source=dags_path, target="/home/airflow/gcs/dags/", type="bind"
        ),
        mock.call(
            source=str(path / "plugins"),
            target="/home/airflow/gcs/plugins/",
            type="bind",
        ),
        mock.call(
            source=str(path / "data"),
            target="/home/airflow/gcs/data/",
            type="bind",
        ),
        mock.call(
            source=gcloud_path,
            target="/home/airflow/.config/gcloud",
            type="bind",
        ),
        mock.call(
            source=str(airflow_db_path),
            target="/home/airflow/airflow/airflow.db",
            type="bind",
        ),
    ]
    actual_mounts = environment.get_image_mounts(
        path, dags_path, gcloud_path, requirements
    )
    assert len(expected_mounts) == len(actual_mounts)
    mocked_mount.assert_has_calls(expected_mounts)


@mock.patch("composer_local_dev.environment.service_v1", autospec=True)
def test_get_software_config_from_environment_api_error(mocked_service):
    error_msg = "Foo error"
    mock_get_environment = mock.Mock()
    mock_get_environment.get_environment.side_effect = (
        api_exception.GoogleAPIError(error_msg)
    )
    mocked_service.EnvironmentsClient.return_value = mock_get_environment
    with pytest.raises(
        errors.ComposerCliError,
        match=constants.COMPOSER_SOFTWARE_CONFIG_API_ERROR.format(
            err=error_msg
        ),
    ):
        environment.get_software_config_from_environment("", "", "")


class TestGetContainer:
    def get_container(self, default_env):
        default_env


class TestGetImageVersion:
    def test_get_image_version_container_missing(self):
        image_version_in_config = "composer-2.0.8-airflow-2.2.30"
        env = mock.Mock()
        env.image_version = image_version_in_config
        env.get_container = mock.Mock(
            side_effect=errors.EnvironmentNotRunningError
        )
        assert image_version_in_config == environment.get_image_version(env)

    def test_get_image_version_no_tags(self):
        image_version_in_config = "composer-2.0.8-airflow-2.2.30"
        env = mock.Mock()
        env.image_version = image_version_in_config
        container = mock.Mock()
        container.image = mock.Mock()
        container.image.tags = []
        env.get_container = mock.Mock(return_value=container)
        assert image_version_in_config == environment.get_image_version(env)

    def test_get_image_version(self):
        image_version_in_config = "composer-2.0.8-airflow-2.2.30"
        image_version_in_container = "composer-2.0.8-airflow-2-2-3"
        expected_image_version = "composer-2.0.8-airflow-2.2.3"
        tag = f"container-name:{image_version_in_container}"
        env = mock.Mock()
        env.image_version = image_version_in_config
        container = mock.Mock()
        container.image = mock.Mock()
        container.image.tags = [tag]
        env.get_container = mock.Mock(return_value=container)
        assert expected_image_version == environment.get_image_version(env)


class TestEnvironmentConfig:
    @mock.patch(
        "composer_local_dev.environment.EnvironmentConfig.load_configuration_from_file"
    )
    @pytest.mark.parametrize(
        "config, error",
        [
            ({}, "composer_project_id"),
            ({"composer_project_id": ""}, "composer_image_version"),
        ],
    )
    def test_from_config_missing_keys(
        self, mocked_load_conf, tmp_path, config, error
    ):
        mocked_load_conf.return_value = config
        exp_error = (
            constants.MISSING_REQUIRED_PARAM_ERROR.format(param=error)
            + constants.ADD_DEBUG_ON_ERROR_INFO
        )
        with pytest.raises(
            errors.MissingRequiredParameterError, match=exp_error
        ):
            environment.EnvironmentConfig(tmp_path, None)

    def test_invalid_config(self):
        env_dir = (
            TEST_DATA_DIR / "one_env" / "composer" / "example_env"
        ).resolve()
        config_path = env_dir / "config.json"
        exp_error = constants.INVALID_CONFIGURATION_FILE_ERROR.format(
            config_path=config_path, error=""
        )
        with pytest.raises(
            errors.FailedToParseConfigError
        ) as err, working_directory(env_dir):
            environment.EnvironmentConfig(env_dir, None)
            assert str(err) == exp_error

    def test_missing_config(self):
        env_dir = (TEST_DATA_DIR / "missing_composer").resolve()
        exp_error = f"Configuration file '{env_dir / 'config.json'}' not found."
        with pytest.raises(errors.ComposerCliError) as err, working_directory(
            env_dir
        ):
            environment.EnvironmentConfig(env_dir, None)
            assert str(err) == exp_error

    @mock.patch(
        "composer_local_dev.environment.EnvironmentConfig.load_configuration_from_file"
    )
    @pytest.mark.parametrize(
        "param, value", [("dag_dir_list_interval", "abc"), ("port", "abc")]
    )
    def test_param_invalid_int(self, mocked_load_conf, tmp_path, param, value):
        valid_config = {
            "composer_image_version": "composer-2.0.25-airflow-2.2.5",
            "composer_location": "us-central1",
            "composer_project_id": "project",
            "dags_path": "/dags/",
            "dag_dir_list_interval": 10,
            "port": 8080,
        }
        valid_config[param] = value
        mocked_load_conf.return_value = valid_config
        exp_error = constants.INVALID_INT_VALUE_ERROR.format(
            param_name=param, value=value
        )
        with pytest.raises(errors.FailedToParseConfigParamIntError) as err:
            environment.EnvironmentConfig(tmp_path, None)
            assert str(err) == exp_error

    @mock.patch(
        "composer_local_dev.environment.EnvironmentConfig.load_configuration_from_file"
    )
    @pytest.mark.parametrize(
        "param, value, allowed_range",
        [
            ("dag_dir_list_interval", -1, "x>=0"),
            ("port", "8000000", "0<=x<=65536"),
        ],
    )
    def test_param_invalid_int_range(
        self, mocked_load_conf, tmp_path, param, value, allowed_range
    ):
        valid_config = {
            "composer_image_version": "composer-2.0.25-airflow-2.2.5",
            "composer_location": "us-central1",
            "composer_project_id": "project",
            "dags_path": "/dags/",
            "dag_dir_list_interval": 10,
            "port": 8080,
        }
        valid_config[param] = value
        mocked_load_conf.return_value = valid_config
        exp_error = constants.INVALID_INT_RANGE_VALUE_ERROR.format(
            param_name=param, value=value, allowed_range=allowed_range
        )
        with pytest.raises(errors.FailedToParseConfigParamIntRangeError) as err:
            environment.EnvironmentConfig(tmp_path, None)
            assert str(err) == exp_error
