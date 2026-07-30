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
import re
import subprocess
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from google.api_core import exceptions as api_exception

from composer_local_dev import constants, errors, utils

GCLOUD_CONFIG = json.dumps(
    {"configuration": {"properties": {"core": {"project": "test123"}}}}
)
GCLOUD_CONFIG_EMPTY_JSON = "{}"
GCLOUD_CONFIG_EMPTY = ""
GCLOUD_INVALID_STRING = "I am not really json"


@mock.patch(
    "subprocess.run",
    autospec=True,
    return_value=mock.Mock(stdout=GCLOUD_CONFIG),
)
def test_get_project_id(mocked_run):
    project_id = "test123"
    assert utils.get_project_id() == project_id
    assert mocked_run.called


@pytest.mark.parametrize("config", [GCLOUD_CONFIG_EMPTY, GCLOUD_INVALID_STRING])
@mock.patch("subprocess.run", autospec=True)
def test_get_project_id_invalid_output(mocked_run, config):
    mocked_run.return_value = mock.Mock(stdout=config)
    exp_error = (
        "Failed to decode gcloud CLI configuration: "
        "Expecting value: line 1 column 1 (char 0)"
        + constants.ADD_DEBUG_ON_ERROR_INFO
    )
    with pytest.raises(errors.ComposerCliError, match=re.escape(exp_error)):
        assert utils.get_project_id()
    assert mocked_run.called


@mock.patch(
    "subprocess.run",
    autospec=True,
    return_value=mock.Mock(stdout=GCLOUD_CONFIG_EMPTY_JSON),
)
def test_get_project_id_empty_config(mocked_run):
    exp_error = (
        "gcloud configuration is missing project id."
        + constants.ADD_DEBUG_ON_ERROR_INFO
    )
    with pytest.raises(errors.ComposerCliError, match=exp_error):
        assert utils.get_project_id()
    assert mocked_run.called


@mock.patch(
    "subprocess.run",
    autospec=True,
    side_effect=subprocess.CalledProcessError(1, "Test message"),
)
def test_get_project_id_error(mocked_run):
    error_from_process = (
        "Command 'Test message' returned non-zero exit status 1"
    )
    exp_error = constants.AUTH_INVALID_ERROR.format(error=error_from_process)
    with pytest.raises(errors.ComposerCliError, match=re.escape(exp_error)):
        utils.get_project_id()
    mocked_run.assert_called()


class TestResolveGcloudConfigPath:
    def test_cloud_sdk_config_set(self):
        config_path = "path/to/config"
        with mock.patch.dict(
            "os.environ", {constants.CLOUD_CLI_CONFIG_PATH_ENV: config_path}
        ):
            actual_config_path = utils.resolve_gcloud_config_path()
        assert config_path == actual_config_path

    @mock.patch(
        "composer_local_dev.environment.utils.is_windows_os", return_value=True
    )
    def test_resolve_path_on_windows(self, mocked_os_check, tmpdir):
        expected_config_path = (tmpdir / "gcloud").mkdir()
        with mock.patch.dict("os.environ", {"APPDATA": str(tmpdir)}):
            actual_config_path = utils.resolve_gcloud_config_path()
        assert str(expected_config_path) == actual_config_path

    @mock.patch.object(pathlib.Path, "is_dir")
    @mock.patch.object(pathlib.Path, "expanduser")
    @mock.patch(
        "composer_local_dev.environment.utils.is_windows_os", return_value=False
    )
    def test_resolve_path_not_on_windows(
        self, mocked_os_check, mocked_expand, mocked_is_dir
    ):
        config_path = os.pathsep.join(["path", "to", "config"])
        mocked_expand.return_value = pathlib.Path(config_path)
        mocked_is_dir.return_value = True
        actual_config_path = utils.resolve_gcloud_config_path()
        assert config_path == actual_config_path

    @mock.patch(
        "composer_local_dev.environment.utils.is_windows_os", return_value=True
    )
    def test_not_existing_gcloud_path(self, mocked_os_check):
        config_path = "i/dont/exist"
        with (
            pytest.raises(
                errors.ComposerCliError,
                match="Could not resolve gcloud config location. "
                "Please use CLOUDSDK_CONFIG environment variable to override "
                "default configuration location.",
            ),
            mock.patch.dict("os.environ", {"APPDATA": config_path}),
        ):
            utils.resolve_gcloud_config_path()


class TestResolveKubeConfigPath:
    def test_kube_config_set_with_env_variable(self):
        config_path = "path/to/config"
        with mock.patch.dict(
            "os.environ", {constants.KUBECONFIG_PATH_ENV: config_path}
        ):
            actual_config_path = utils.resolve_kube_config_path()
        assert config_path == actual_config_path

    @mock.patch(
        "composer_local_dev.constants.KUBECONFIG_PATH_ENV", spec_set=True
    )
    def test_kube_config_set_without_env_variable(self, mocked_kube_config_env):
        actual_config_path = utils.resolve_kube_config_path()
        assert actual_config_path is None


class TestAsserEnvironmentNameIsValid:
    @pytest.mark.parametrize(
        "name, message",
        [
            (
                "1",
                constants.ENVIRONMENT_NAME_TOO_SHORT_ERROR.format(env_name="1"),
            ),
            (
                "a" * 41,
                constants.ENVIRONMENT_NAME_TOO_LONG_ERROR.format(
                    env_name="a" * 41
                ),
            ),
            (
                "abc%#",
                constants.ENVIRONMENT_NAME_NOT_VALID_ERROR.format(
                    env_name="abc%#"
                ),
            ),
        ],
    )
    def test_invalid_names(self, name, message):
        with pytest.raises(errors.ComposerCliError, match=re.escape(message)):
            utils.assert_environment_name_is_valid(name)

    @pytest.mark.parametrize("name", ["5" * 3, "rG-_" * 10])
    def test_valid_names(self, name):
        utils.assert_environment_name_is_valid(name)


class TestGetAirflowComposerVersions:
    def test_get_airflow_composer_versions_error(self):
        image_version = "wrong-image-name"
        with pytest.raises(
            errors.ComposerCliError,
            match=re.escape(constants.INVALID_IMAGE_VERSION_ERROR),
        ):
            utils.get_airflow_composer_versions(image_version)

    @pytest.mark.parametrize(
        "image_version, exp_composer_v, exp_airflow_v",
        [
            ("composer-2.0.8-airflow-2.2.3", "2.0.8", "2.2.3"),
            ("composer-2.9.8-airflow-2.10.2", "2.9.8", "2.10.2"),
            ("composer-3-airflow-2.10.2-build.10", "3", "2.10.2-build.10"),
        ],
    )
    def test_get_airflow_composer_versions(
        self, image_version, exp_composer_v, exp_airflow_v
    ):
        airflow_v, composer_v = utils.get_airflow_composer_versions(
            image_version
        )
        assert exp_airflow_v == airflow_v
        assert exp_composer_v == composer_v


def get_image_version_mock(version_id, day, month, year):
    image_version = mock.Mock()
    image_version.image_version_id = version_id
    image_version.release_date = mock.Mock()
    image_version.release_date.day = day
    image_version.release_date.month = month
    image_version.release_date.year = year
    return utils.ImageVersion(image_version)


def test_filter_image_versions():
    def get_supported_image_version_mock(image_version, should_be_supported):
        return (
            get_image_version_mock(image_version, 1, 1, 2022),
            should_be_supported,
        )

    versions = [
        get_supported_image_version_mock("composer-2.0.23-airflow-2.2.1", True),
        get_supported_image_version_mock("composer-2.0.23-airflow-2.2.2", True),
        get_supported_image_version_mock(
            "composer-1.0.23-airflow-2.2.3", False
        ),
        get_supported_image_version_mock(
            "composer-1.0.22-airflow-2.2.1", False
        ),
        get_supported_image_version_mock("composer-2.0.22-airflow-2.2.2", True),
        get_supported_image_version_mock(
            "composer-3-airflow-2.10.2-build.5", False
        ),
        get_supported_image_version_mock(
            "composer-3-airflow-2.10.2-build.20", True
        ),
        get_supported_image_version_mock(
            "composer-3-airflow-2.10.5-build.0", True
        ),
        get_supported_image_version_mock(
            "composer-3-airflow-2.11.0-build.0", True
        ),
        get_supported_image_version_mock(
            "composer-3-airflow-3.0.0-build.50", False
        ),
        get_supported_image_version_mock(
            "composer-3-airflow-3.1.0-build.7", False
        ),
        get_supported_image_version_mock(
            "composer-3-airflow-3.1.0-build.8", True
        ),
        get_supported_image_version_mock(
            "composer-3-airflow-3.1.1-build.0", True
        ),
    ]
    expected_versions = [
        version for (version, supported) in versions if supported
    ]
    all_versions = [version for (version, _) in versions]
    filtered = utils.filter_image_versions(all_versions)
    assert filtered == expected_versions


def test_sort_and_limit_image_versions():
    versions = [
        get_image_version_mock("composer-2.0.23-airflow-2.2.5", 1, 1, 2022),
        get_image_version_mock("composer-2.0.23-airflow-2.2.5", 1, 2, 2022),
        get_image_version_mock("composer-2.0.23-airflow-2.2.5", 1, 1, 2023),
        get_image_version_mock("composer-2.0.22-airflow-2.2.5", 1, 1, 2022),
        get_image_version_mock("composer-2.0.23-airflow-2.2.5", 2, 1, 2022),
    ]
    sorted_versions = utils.sort_and_limit_image_versions(versions, 1)
    assert 1 == len(sorted_versions)
    assert (
        "composer-2.0.23-airflow-2.2.5" == sorted_versions[0].image_version_id
    )
    assert "01/01/2023" == str(sorted_versions[0].release_date)
    sorted_versions = utils.sort_and_limit_image_versions(versions, 10)
    assert 5 == len(sorted_versions)
    assert (
        "composer-2.0.23-airflow-2.2.5" == sorted_versions[1].image_version_id
    )
    assert "01/02/2022" == str(sorted_versions[1].release_date)


@mock.patch("composer_local_dev.utils.service_v1", autospec=True)
def test_get_image_versions_api_error(mocked_service):
    error_msg = "Foo error"
    mock_client = mock.Mock()
    mock_client.list_image_versions.side_effect = api_exception.GoogleAPIError(
        error_msg
    )
    mocked_service.ImageVersionsClient.return_value = mock_client
    with pytest.raises(
        errors.ComposerCliError,
        match=constants.LIST_VERSIONS_API_ERROR.format(err=error_msg),
    ):
        utils.get_image_versions("", "", False)


@pytest.mark.parametrize(
    "path_str, expected",
    [
        (f"composer_dev_{constants.SQLITE_AIRFLOW_HOME_VOLUME_NAME}", True),
        (f"composer_dev_{constants.POSTGRES_DATA_VOLUME_NAME}", True),
        ("C:/Users/User/my_project/dags", False),
        ("relateive/path/to/somewhere", False),
    ],
)
def test_is_podman_volume(path_str, expected):
    host_path = pathlib.Path(path_str)
    assert utils.is_podman_volume(host_path) is expected


def test_enforce_podman_volume_type():
    mounts = [
        {
            "Source": f"some_prefix_{constants.POSTGRES_DATA_VOLUME_NAME}",
            "Target": "/var/lib/postgresql/data",
            "Type": "bind",
        },
        {
            "Source": "C:/Users/User/project/dags",
            "Target": "/opt/airflow/dags",
            "Type": "bind",
        },
    ]

    utils.enforce_podman_volume_type(mounts)

    assert mounts[0]["Type"] == "volume"
    assert mounts[1]["Type"] == "bind"


@mock.patch(
    "composer_local_dev.environment.utils.is_windows_os", return_value=False
)
def test_is_podman_windows_return_false_on_linux(mocked_os_check):
    mock_client = MagicMock()

    utils.is_podman_windows.cache_clear()

    assert utils.is_podman_windows(mock_client) is False


@mock.patch(
    "composer_local_dev.environment.utils.is_windows_os", return_value=True
)
def test_is_podman_windows_detect_podman_on_windows(mocked_os_check):
    mock_client = MagicMock()
    mock_client.version.return_value = {
        "Components": [{"Name": "Podman Engine", "Version": "5.1.1"}]
    }

    utils.is_podman_windows.cache_clear()
    assert utils.is_podman_windows(mock_client) is True


@patch("docker.from_env")
@patch("time.sleep")
def test_restart_docker_client(mock_sleep, mock_from_env):
    mock_old_client = MagicMock()
    mock_new_client = MagicMock()
    mock_new_client.ping.return_value = True

    mock_from_env.return_value = mock_new_client

    returned_client = utils.restart_docker_client(mock_old_client)

    mock_old_client.close.assert_called_once()
    mock_new_client.ping.assert_called()
    assert returned_client is mock_new_client
