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
import enum

# The name of environment variable with custom configuration path
CLOUD_CLI_CONFIG_PATH_ENV = "CLOUDSDK_CONFIG"

OPERATION_TIMEOUT_SECONDS = (
    300  # TODO: Check if we need such timeout, or any timeout at all
)

BAD_REQUEST_ERROR_CODE = 400
CONFLICT_ERROR_CODE = 409
SERVER_ERROR_CODE = 500


class ContainerStatus(str, enum.Enum):
    RUNNING = "running"
    CREATED = "created"


COMPOSER_VERSIONING_DOCS_LINK = "https://cloud.google.com/composer/docs/concepts/versioning/composer-versions"
COMPOSER_FAQ_MOUNTING_LINK = "https://cloud.google.com/composer/docs/composer-2/run-local-airflow-environments#troubleshooting-homebrew"
IMAGE_VERSION_PATTERN = (
    "composer-([1-9]+\.[0-9]+\.[0-9]+)-airflow-([1-9]+[\.|-][0-9]+[\.|-][0-9]+)"
)
ARTIFACT_REGISTRY_IMAGE_URL = (
    "projects/cloud-airflow-releaser/"
    "locations/us/repositories/"
    "airflow-worker-scheduler-{airflow_v}/packages/"
    "airflow-worker-scheduler-{airflow_v}/tags/"
    "composer-{composer_v}-airflow-{airflow_v}"
)
DOCKER_REGISTRY_IMAGE_TAG = (
    "us-docker.pkg.dev/cloud-airflow-releaser/"
    "airflow-worker-scheduler-{airflow_v}/"
    "airflow-worker-scheduler-{airflow_v}:"
    "composer-{composer_v}-airflow-{airflow_v}"
)

AIRFLOW_HOME = "/home/airflow"
ENTRYPOINT_PATH = f"{AIRFLOW_HOME}/entrypoint.sh"

CREATE_MESSAGE_HINT = """
Run following command to check how to create new environment:
  $ composer-dev create --help
"""
CREATE_MESSAGE = """
Created environment under {env_dir}. 
You can now start it using following command:

$ composer-dev start {env_name}

You can modify generated files to change your environment settings. 
Common settings are defined in {config_path}.
PyPi extra packages are listed in {requirements_path}.
Airflow overrides and environment variables are stored in {env_variables_path}.

You can put your plugins and data to plugins and data directories 
available at {env_dir}.
DAGs can be updated at {dags_path} path.

To apply changes done to environment config and PyPI dependencies 
restart environment using following command:

$ composer-dev restart {env_name}
"""
START_MESSAGE = """
Started [bold]{env_name}[/] environment.

1. You can put your DAGs in {dags_path}
2. Access Airflow at http://localhost:{port}
"""
# TODO: Fill source environment info
DESCRIBE_ENV_MESSAGE = """
Composer [bold]{name}[/] environment is in state: {state}.
{web_url}
Image version: {image_version}
Dags directory: {dags_path}.
The environment is using credentials from gcloud located at {gcloud_path}.

This information is based on the data available in the
environments configurations.
"""
WEBSERVER_URL_MESSAGE = (
    "\nWeb-server can be accessed at http://localhost:{port}\n"
)

CONTAINER_NAME = "composer-local-dev"
IMAGE_TAG_PERMISSION_DENIED_WARN = (
    "Received permission denied when checking "
    "image existence for {image_tag}"
)
CREATING_DAGS_PATH_WARN = (
    "Dags path '{dags_path}' does not exist. It will be created."
)
DAGS_PATH_NOT_PROVIDED_WARN = (
    "No dags directory provided, using default dags directory."
)
ADD_DEBUG_ON_ERROR_INFO = "\n\nTo print debug messages please add --debug flag."
DAGS_PATH_NOT_EXISTS_ERROR = (
    "Dags path does not exist or is not a directory: {dags_path}"
)
FAILED_TO_GET_DOCKER_PORT_WARN = (
    "Failed to retrieve used port from the Docker daemon, "
    "using port from the environment configuration."
)
ENVIRONMENT_NAME_TOO_SHORT_ERROR = (
    "Environment name '{env_name}' is too short (min. 3 characters required)."
)
ENVIRONMENT_NAME_TOO_LONG_ERROR = (
    "Environment name '{env_name}' is too long (max. 40 characters allowed)."
)
ENVIRONMENT_NAME_NOT_VALID_ERROR = (
    "Environment name '{env_name}' is not a valid environment name. "
    "Environment name can only consist of alphanumeric characters, "
    "underscores and hyphens."
)
COMPOSER_SOFTWARE_CONFIG_API_ERROR = (
    "Failed to retrieve Cloud Composer environment configuration: {err}"
)
LIST_VERSIONS_API_ERROR = "Failed to list available versions: {err}"
ENVIRONMENT_DIR_NOT_FOUND_ERROR = (
    "'{env_dir}' directory not found.{create_help}"
)
ENVIRONMENT_DIR_EMPTY_ERROR = (
    "No environment detected in '{env_dir}'.{create_help}"
)
ENVIRONMENTS_NOT_FOUND = "No environments could be found at the path: {path}"
ENVIRONMENTS_FOUND = (
    "Following local Composer environments could be found at the path: {path}\n"
)
ENVIRONMENT_PATH_NOT_FOUND_ERROR = (
    "'{env_path}' directory not found. "
    "Please check that correct environment name was provided and "
    "the environment exists.{create_help}"
)
ENVIRONMENT_NOT_SELECTED_ERROR = (
    "'{env_dir}' directory contains more than one environment but "
    "environment name was not provided. Provide environment argument "
    "to select one of the existing environments:\n"
    "    {env_names}"
)
ENVIRONMENT_ALREADY_RUNNING = (
    "Composer local development for environment '{name}' is already "
    "running. Stop or restart it if you want to run it."
)
GCLOUD_CONFIG_NOT_FOUND_ERROR = (
    "Could not resolve gcloud config location. "
    "Please use CLOUDSDK_CONFIG environment variable to override default "
    "configuration location."
)
PORT_IN_USE_ERROR = (
    "Port {port} is already in use. "
    "Please use different port or close application using port {port}.\n"
    "You can select different port by using --port option when starting "
    "environment."
)
ENVIRONMENT_FAILED_TO_START_ERROR = "Environment failed to start."
ENV_DID_NOT_START_TIMEOUT_ERROR = (
    "Environment did not start in {seconds} seconds."
)
ENV_NOT_RUNNING = "Failed to run command: environment not running."
MISSING_REQUIRED_PARAM_ERROR = (
    "Missing required parameter: '{param}' in the environment 'config.json' "
    "configuration file."
)
INVALID_CONFIGURATION_FILE_ERROR = (
    "Failed to parse configuration file: '{config_path}' with an error: {error}"
)
INVALID_ENV_VARIABLES_FILE_ERROR = (
    "Could not parse the file containing environment variables "
    "({env_file_path}). Line '{line}' is invalid."
    "Each line should contain a key-value pair, eg. FOO=BAR."
)
INVALID_INT_VALUE_ERROR = (
    "Invalid value for '{param_name}' configuration value."
    " '{value}' is not a valid integer."
)
INVALID_INT_RANGE_VALUE_ERROR = (
    "Invalid value for '{param_name}' configuration value. "
    "{value} is not in the range {allowed_range}."
)
INVALID_IMAGE_VERSION_ERROR = (
    "Composer version must match `composer-x.y.z-airflow-a.b.c` pattern."
)
IMAGE_TAG_DOES_NOT_EXIST_ERROR = (
    "Composer version {image_tag} seems not to be valid. Please make sure to "
    "use existing Cloud Composer version. You can see the list of "
    "available versions by running:\n\n"
    "    $ composer-dev list-available-versions"
)
AUTH_INVALID_ERROR = (
    "Could not validate authentication data: {error}.\n"
    "Please check your internet connection.\n"
    "To obtain and export new credentials please run following two commands:\n\n"
    "    $ gcloud auth login\n"
    "    $ gcloud auth application-default login\n\n"
    "To obtain new credentials."
)
PULL_IMAGE_MSG = (
    "[bold green]Pulling Composer image. It can take a few minutes."
)
DOCKER_NOT_AVAILABLE_ERROR = (
    "Docker not available or failed to start. Please ensure docker service "
    "is installed and running. Error: {error}"
)
DOCKER_CONTAINER_MEMORY_LIMIT = "4g"
NOT_MODIFIABLE_ENVIRONMENT_VARIABLES = {
    "AIRFLOW_HOME",
    "AIRFLOW__CORE__EXECUTOR",
}
LIST_COMMAND_EPILOG = (
    "\nRun describe command with the environment name to see the detailed "
    "information and potential configuration errors.\n\n"
    "* Based on the data available in the environments configuration files."
)
IMAGE_VERSION_CONTAINER_MISSING = (
    "Environment {env_name} container does not exist. "
    "Using image version from the configuration file."
)
IMAGE_VERSION_TAG_MISSING = (
    "Failed to read image version from the container tag for {env_name} "
    "environment. Using image version from the configuration file."
)
DOCKER_PERMISSION_ERROR_HINT = (
    "\nPossible reason is that composer-dev was installed in the path that is "
    "not available to Docker. See {docs_faq_url} for more information."
)
REMOVE_ENV_CONFIRMATION_PROMPT = (
    "This will delete directory '{env_path}' and all of its content "
    "(data/plugins/dags). This command will not delete any Docker images."
)
REMOVING_CONTAINER_MSG = "The environment is running. Killing the container..."
USE_FORCE_TO_REMOVE_ERROR = (
    "The environment is running. "
    "Use --force flag if you want to stop environment and remove it."
)
MALFORMED_CONFIG_REMOVING_CONTAINER = (
    "Failed to load environment configuration. Environment Docker container "
    "could not be removed."
)
