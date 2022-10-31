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
import logging
import os
import pathlib
import re
import subprocess
import sys
from functools import total_ordering
from typing import List, Optional, Tuple

import click
import rich.box
import rich.table
from google.api_core import exceptions as api_exception
from google.cloud.orchestration.airflow import service_v1
from rich.logging import RichHandler

from composer_local_dev import constants, errors

LOG = logging.getLogger(__name__)

# The name of the Cloud SDK shell script
_CLOUD_CLI_POSIX_COMMAND = "gcloud"
_CLOUD_CLI_WINDOWS_COMMAND = "gcloud.cmd"

# The command to get the Cloud SDK configuration
_CLOUD_CLI_CONFIG_COMMAND = "config config-helper --format json"

LOG_FORMAT = "%(name)s:%(message)s"
LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


@total_ordering
class ImageVersion:
    def __init__(self, image_version: service_v1.types.ImageVersion):
        self.image_version_id = image_version.image_version_id
        self.release_date = ImageVersionReleaseDate(image_version.release_date)

    def __eq__(self, other):
        return (
            self.release_date == other.release_date
            and self.image_version_id == other.image_version_id
        )

    def __lt__(self, other):
        if self.release_date == other.release_date:
            return self.image_version_id < other.image_version_id
        return self.release_date < other.release_date


@total_ordering
class ImageVersionReleaseDate:
    def __init__(self, release_date):
        self.release_date = release_date

    def __str__(self):
        return (
            f"{self.release_date.day:0>2}/{self.release_date.month:0>2}/"
            f"{self.release_date.year}"
        )

    def __eq__(self, other):
        return self.release_date == other.release_date

    def __lt__(self, other):
        return (
            self.release_date.year,
            self.release_date.month,
            self.release_date.day,
        ) < (
            other.release_date.year,
            other.release_date.month,
            other.release_date.day,
        )


def is_windows_os() -> bool:
    return os.name == "nt"


def is_linux_os() -> bool:
    return sys.platform.startswith("linux")


def gcloud_cmd() -> str:
    if is_windows_os():
        return _CLOUD_CLI_WINDOWS_COMMAND
    return _CLOUD_CLI_POSIX_COMMAND


def get_project_id() -> Optional[str]:
    """Gets the project ID from the Cloud CLI."""
    try:
        output = subprocess.run(
            [gcloud_cmd()] + _CLOUD_CLI_CONFIG_COMMAND.split(),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        LOG.debug("Cloud CLI output: %s", output)
    except (subprocess.CalledProcessError, OSError, IOError) as err:
        logging.debug(
            "Failed to get project ID from the Cloud CLI.", exc_info=True
        )
        raise errors.InvalidAuthError(err)

    try:
        configuration = json.loads(output)
    except ValueError as err:
        raise errors.ComposerCliError(
            f"Failed to decode gcloud CLI configuration: {err}"
        ) from None

    try:
        project_id = configuration["configuration"]["properties"]["core"][
            "project"
        ]
        LOG.info("Using GCP project %s", project_id)
        return project_id
    except KeyError:
        raise errors.ComposerCliError(
            "gcloud configuration is missing project id."
        ) from None


def resolve_gcloud_config_path() -> str:
    """
    Returns the absolute path the Cloud CLI's configuration directory.
    """
    if constants.CLOUD_CLI_CONFIG_PATH_ENV in os.environ:
        return os.environ[constants.CLOUD_CLI_CONFIG_PATH_ENV]

    if is_windows_os() and "APPDATA" in os.environ:
        config_path = pathlib.Path(os.environ["APPDATA"], "gcloud")
    else:
        config_path = pathlib.Path("~/.config/gcloud").expanduser()
    # TODO (b/234553956) Check if found directory is correct gcloud config
    if config_path.is_dir():
        return str(config_path)
    raise errors.ComposerCliError(constants.GCLOUD_CONFIG_NOT_FOUND_ERROR)


def assert_environment_name_is_valid(env_name: str):
    """
    Asserts that environment name is a valid name.

    Valid name uses only characters from [A-Za-z0-9_-] range and its length
    is between 3 and 40 characters.
    """
    if len(env_name) < 3:
        raise errors.ComposerCliError(
            constants.ENVIRONMENT_NAME_TOO_SHORT_ERROR.format(env_name=env_name)
        )
    if len(env_name) > 40:
        raise errors.ComposerCliError(
            constants.ENVIRONMENT_NAME_TOO_LONG_ERROR.format(env_name=env_name)
        )
    if re.search("[^A-Za-z0-9_-]", env_name):
        raise errors.ComposerCliError(
            constants.ENVIRONMENT_NAME_NOT_VALID_ERROR.format(env_name=env_name)
        )


def get_airflow_composer_versions(image_version: str) -> Tuple[str, str]:
    """
    Get airflow and composer versions from image_version.

    Args:
        image_version: Image version in format of 'composer-x.y.z-airflow-a.b.c'

    Returns:
        airflow_v: Airflow version (in x-y-z format).
        composer_v: Composer version (in a.b.c format).
    """
    version_match = re.match(constants.IMAGE_VERSION_PATTERN, image_version)
    if not version_match:
        raise errors.ComposerCliError(constants.INVALID_IMAGE_VERSION_ERROR)
    composer_v, airflow_v = version_match.group(1), version_match.group(2)
    airflow_v = airflow_v.replace(".", "-")
    return airflow_v, composer_v


def format_airflow_version_dotted(airflow_v: str) -> str:
    """Format Airflow version to use '.' instead of '-'."""
    return airflow_v.replace("-", ".")


def get_image_version_tag(airflow_v: str, composer_v: str) -> str:
    """
    Returns Composer image version tag created from
    Airflow and Composer versions.
    """
    return f"composer-{composer_v}-airflow-{airflow_v}"


def get_environment_status_table(envs_status: List) -> rich.table.Table:
    """Get Environment status table to print."""
    table = rich.table.Table(box=rich.box.MINIMAL)
    for col in ("Environment Name", "Version*", "State"):
        table.add_column(col)
    for env_status in envs_status:
        table.add_row(env_status.name, env_status.version, env_status.status)
    return table


def filter_image_versions(image_versions: List) -> List:
    """
    Filter out Composer 1 versions out of list of image versions.
    """
    return [
        version
        for version in image_versions
        if not version.image_version_id.startswith("composer-1")
    ]


def sort_and_limit_image_versions(image_versions: List, limit: int) -> List:
    """
    Sort image versions by date and return only first ``limit`` image versions.
    """
    return sorted(image_versions, reverse=True)[:limit]


def get_image_versions_table(image_versions: List) -> rich.table.Table:
    """Get image versions table to print."""
    table = rich.table.Table(box=rich.box.MINIMAL)
    for col in ("Image version", "Release Date"):
        table.add_column(col)
    for image_version in image_versions:
        table.add_row(
            image_version.image_version_id, str(image_version.release_date)
        )
    return table


def wrap_status_in_color(status: str) -> str:
    """
    Wrap container status in color tags.
    Used to pretty print container status in the cli."""
    status_color = (
        "green" if status == constants.ContainerStatus.RUNNING else "red"
    )
    return f"[bold {status_color}]{status}[/]"


def get_log_level(verbose: bool, debug: bool):
    """
    Get logging log level for our package depending on
    verbose and debug flags values.
    """
    if debug:
        return logging.DEBUG
    if verbose:
        return logging.INFO
    return logging.WARNING


def get_external_log_level(debug: bool):
    """
    Get logging log level for external packages depending on debug flag value.
    """
    if debug:
        return logging.DEBUG
    return logging.WARNING


def setup_logging(verbose: bool, debug: bool):
    log_level = get_log_level(verbose, debug)
    external_log_level = get_external_log_level(debug)
    logging.basicConfig(
        level=log_level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=[RichHandler()],
    )
    logging.captureWarnings(True)
    logging.getLogger("docker").setLevel(external_log_level)
    logging.getLogger("urllib3").setLevel(external_log_level)


def get_image_versions(
    project: str, location: str, include_past_releases: bool
):
    """
    Query Composer API to get list of released image versions for given
    project and location.
    """
    client = service_v1.ImageVersionsClient()
    parent = f"projects/{project}/locations/{location}"
    request = service_v1.ListImageVersionsRequest(
        parent=parent, include_past_releases=include_past_releases
    )
    try:
        page_result = client.list_image_versions(request=request)
    except api_exception.GoogleAPIError as err:
        raise errors.ComposerCliError(
            constants.LIST_VERSIONS_API_ERROR.format(err=str(err))
        )
    return [ImageVersion(response) for response in page_result]


def resolve_project_id(project_id: Optional[str]) -> str:
    """
    Resolve optional ``project_id``. If ``project_id`` is None, retrieve its
    value from Google Cloud CLI.
    """
    if project_id is not None:
        return project_id
    LOG.info(
        "Project id was not provided. It will be retrieved using Cloud CLI."
    )
    try:
        return get_project_id()
    except errors.ComposerCliError as err:
        raise click.UsageError(
            f"Please provide Google Cloud project id "
            f"(using '-p' / '--project' option). Failed to retrieve "
            f"project id from gcloud configuration:\n{err}"
        )
