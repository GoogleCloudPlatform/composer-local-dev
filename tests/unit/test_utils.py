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
        with pytest.raises(
            errors.ComposerCliError,
            match="Could not resolve gcloud config location. "
            "Please use CLOUDSDK_CONFIG environment variable to override "
            "default configuration location.",
        ), mock.patch.dict("os.environ", {"APPDATA": config_path}):
            utils.resolve_gcloud_config_path()


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
    def test_get_airflow_composer_versions(self):
        image_version = "wrong-image-name"
        with pytest.raises(
            errors.ComposerCliError, match=constants.INVALID_IMAGE_VERSION_ERROR
        ):
            utils.get_airflow_composer_versions(image_version)

    def test_get_airflow_composer_versions_inv(self):
        image_version = "composer-2.0.8-airflow-2.2.3"
        exp_airflow_v = "2-2-3"
        exp_composer_v = "2.0.8"
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
    versions = [
        get_image_version_mock("composer-2.0.23-airflow-2.2.1", 1, 1, 2022),
        get_image_version_mock("composer-2.0.23-airflow-2.2.2", 1, 2, 2022),
        get_image_version_mock("composer-1.0.23-airflow-2.2.3", 1, 1, 2023),
        get_image_version_mock("composer-1.0.22-airflow-2.2.1", 1, 1, 2022),
        get_image_version_mock("composer-2.0.22-airflow-2.2.2", 2, 1, 2022),
    ]
    expected_versions = [versions[0], versions[1], versions[4]]
    filtered = utils.filter_image_versions(versions)
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
