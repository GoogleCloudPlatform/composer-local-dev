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

import getpass
import io
import json
import logging
import os
import pathlib
import platform
import tarfile
import time
import warnings
from typing import Dict, List, Optional, Tuple, Union

import docker
from docker import errors as docker_errors
from docker.types import Mount
from google.api_core import exceptions as api_exception
from google.auth import exceptions as auth_exception
from google.cloud import artifactregistry_v1
from google.cloud.orchestration.airflow import service_v1

from composer_local_dev import console, constants, errors, files, utils

LOG = logging.getLogger(__name__)
DOCKER_FILES = pathlib.Path(__file__).parent / "docker_files"


def timeout_occurred(start_time):
    """Returns whether time since start is greater than OPERATION_TIMEOUT."""
    return time.time() - start_time >= constants.OPERATION_TIMEOUT_SECONDS


def get_image_mounts(
    env_path: pathlib.Path,
    dags_path: str,
    gcloud_config_path: str,
    requirements: pathlib.Path,
) -> List[docker.types.Mount]:
    """
    Return list of docker volumes to be mounted inside container.
    Following paths are mounted:
     - requirements for python packages to be installed
     - dags, plugins and data for paths which contains dags, plugins and data
     - gcloud_config_path which contains user credentials to gcloud
     - environment airflow sqlite db file location
    """
    mount_paths = {
        requirements: "composer_requirements.txt",
        dags_path: "gcs/dags/",
        env_path / "plugins": "gcs/plugins/",
        env_path / "data": "gcs/data/",
        gcloud_config_path: ".config/gcloud",
        env_path / "airflow.db": "airflow/airflow.db",
    }
    return [
        docker.types.Mount(
            source=str(source),
            target=f"{constants.AIRFLOW_HOME}/{target}",
            type="bind",
        )
        for source, target in mount_paths.items()
    ]


def get_default_environment_variables(
    dag_dir_list_interval: int, project_id: str
) -> Dict:
    """Return environment variables that will be set inside container."""
    return {
        "AIRFLOW__API__AUTH_BACKEND": "airflow.api.auth.backend.default",
        "AIRFLOW__WEBSERVER__EXPOSE_CONFIG": "true",
        "AIRFLOW__CORE__LOAD_EXAMPLES": "false",
        "AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL": dag_dir_list_interval,
        "AIRFLOW__CORE__DAGS_FOLDER": "/home/airflow/gcs/dags",
        "AIRFLOW__CORE__PLUGINS_FOLDER": "/home/airflow/gcs/plugins",
        "AIRFLOW__CORE__DATA_FOLDER": "/home/airflow/gcs/data",
        "AIRFLOW__WEBSERVER__RELOAD_ON_PLUGIN_CHANGE": "True",
        "COMPOSER_PYTHON_VERSION": "3",
        # By default, the container runs as the user `airflow` with UID 999. Set
        # this env variable to "True" to make it run as the current host user.
        "COMPOSER_CONTAINER_RUN_AS_HOST_USER": "False",
        "COMPOSER_HOST_USER_NAME": f"{getpass.getuser()}",
        "COMPOSER_HOST_USER_ID": f"{os.getuid() if platform.system() != 'Windows' else ''}",
        "AIRFLOW_HOME": "/home/airflow/airflow",
        "AIRFLOW_CONN_GOOGLE_CLOUD_DEFAULT": f"google-cloud-platform://?"
        f"extra__google_cloud_platform__project={project_id}&"
        f"extra__google_cloud_platform__scope="
        f"https://www.googleapis.com/auth/cloud-platform",
    }


def parse_env_variable(
    line: str, env_file_path: pathlib.Path
) -> Tuple[str, str]:
    """Parse line in format of key=value and return (key, value) tuple."""
    try:
        key, value = line.split("=", maxsplit=1)
    except ValueError:
        raise errors.FailedToParseVariablesError(env_file_path, line)
    return key.strip(), value.strip()


def load_environment_variables(env_dir_path: pathlib.Path) -> Dict:
    """
    Load environment variable to be sourced in the local Composer environment.
    Raises an error if the variables.env file does not exist
    in the ``env_dir_path``.
    Args:
        env_dir_path (pathlib.Path): Path to the local composer environment.

    Returns:
        Dict:
            Environment variables.
    """
    env_file_path = env_dir_path / "variables.env"
    LOG.info("Loading environment variables from %s", env_file_path)
    if not env_file_path.is_file():
        raise errors.ComposerCliError(
            f"Environment variables file '{env_file_path}' not found."
        )
    env_vars = dict()
    with open(env_file_path) as fp:
        for line in fp:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, value = parse_env_variable(line, env_file_path)
            if key in constants.NOT_MODIFIABLE_ENVIRONMENT_VARIABLES:
                LOG.warning(
                    "'%s' environment variable cannot be set "
                    "and will be ignored.",
                    key,
                )
            else:
                env_vars[key] = value
    return env_vars


def filter_not_modifiable_env_vars(env_vars: Dict) -> Dict:
    """
    Filter out environment variables that cannot be modified by user.
    """
    filtered_env_vars = dict()
    for key, val in env_vars.items():
        if key in constants.NOT_MODIFIABLE_ENVIRONMENT_VARIABLES:
            LOG.warning(
                "'%s' environment variable cannot be set and will be ignored.",
                key,
            )
        else:
            filtered_env_vars[key] = val
    return filtered_env_vars


def get_software_config_from_environment(
    project: str, location: str, environment: str
):
    """Get software configuration from the Composer environment.

    Args:
        project (str): Composer GCP Project ID.
        location (str): Location of the Composer environment.
        environment (str): Composer environment name.

    Returns:
        SoftwareConfig: Software configuration of the Composer environment.
    """
    LOG.info("Getting Cloud Composer environment configuration.")
    client = service_v1.EnvironmentsClient()

    name = f"projects/{project}/locations/{location}/environments/{environment}"
    request = service_v1.GetEnvironmentRequest(name=name)
    LOG.debug(f"GetEnvironmentRequest: %s", request)

    try:
        response = client.get_environment(request=request)
    except api_exception.GoogleAPIError as err:
        raise errors.ComposerCliError(
            constants.COMPOSER_SOFTWARE_CONFIG_API_ERROR.format(err=str(err))
        )
    LOG.debug(f"GetEnvironmentResponse: %s", response)
    return response.config.software_config


def parse_airflow_override_to_env_var(airflow_override: str) -> str:
    """
    Parse airflow override variable name in format of section-key to
    AIRFLOW__SECTION__KEY.
    """
    section, key = airflow_override.split("-", maxsplit=1)
    return f"AIRFLOW__{section.upper()}__{key.upper()}"


def get_airflow_overrides(software_config):
    """
    Returns dictionary with environment variable names and
    their values mapped from Airflow overrides in Composer Software Config.
    """
    return {
        parse_airflow_override_to_env_var(k): v
        for k, v in software_config.airflow_config_overrides.items()
    }


def get_env_variables(software_config):
    """
    Returns dictionary with environment variable names (with unset values)
    mapped from Airflow environment variables in Composer Software Config.
    """
    return {k: "" for k, _ in software_config.env_variables.items()}


def assert_image_exists(image_version: str):
    """Asserts that image version exists.

    Raises if the image does not exist.
    Warns if the API error occurs, or we cannot access to Artifact Registry.
    Args:
        image_version: Image version in format of 'composer-x.y.z-airflow-a.b.c'
    """
    airflow_v, composer_v = utils.get_airflow_composer_versions(image_version)
    image_tag = utils.get_image_version_tag(airflow_v, composer_v)
    LOG.info("Asserting that %s composer image version exists", image_tag)
    image_url = constants.ARTIFACT_REGISTRY_IMAGE_URL.format(
        airflow_v=airflow_v, composer_v=composer_v
    )
    client = artifactregistry_v1.ArtifactRegistryClient()
    request = artifactregistry_v1.GetTagRequest(name=image_url)
    LOG.debug(f"GetTagRequest for %s: %s", image_tag, str(request))
    try:
        client.get_tag(request=request)
    except api_exception.NotFound:
        raise errors.ImageNotFoundError(image_version=image_tag) from None
    except api_exception.PermissionDenied:
        warnings.warn(
            constants.IMAGE_TAG_PERMISSION_DENIED_WARN.format(
                image_tag=image_tag
            )
        )
    except (
        auth_exception.GoogleAuthError,
        api_exception.GoogleAPIError,
    ) as err:
        raise errors.InvalidAuthError(err)


def get_docker_image_tag_from_image_version(image_version: str) -> str:
    """
    Parse image version to Airflow and Composer versions and return image tag
    with those versions if it exists.

    Args:
        image_version: Image version in format of 'composer-x.y.z-airflow-a.b.c'

    Returns:
        Composer image tag in Artifact Registry
    """
    airflow_v, composer_v = utils.get_airflow_composer_versions(image_version)
    return constants.DOCKER_REGISTRY_IMAGE_TAG.format(
        airflow_v=airflow_v, composer_v=composer_v
    )


def is_mount_permission_error(error: docker_errors.APIError) -> bool:
    """Checks if error is possibly a Docker mount permission error."""
    return (
        error.is_client_error()
        and error.response.status_code == constants.BAD_REQUEST_ERROR_CODE
        and "invalid mount config" in error.explanation
    )


def copy_entrypoint_to_container(container, src: pathlib.Path) -> None:
    """Copy entrypoint file to Docker container."""
    logging.debug("Copying entrypoint file to Docker container.")
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w|") as tar, open(src, "rb") as f:
        info = tar.gettarinfo(fileobj=f)
        info.name = "entrypoint.sh"
        tar.addfile(info, f)
    container.put_archive(constants.AIRFLOW_HOME, stream.getvalue())


class EnvironmentStatus:
    def __init__(self, name: str, version: str, status: str):
        self.name = name
        self.version = version
        self.status = status.capitalize()


def get_image_version(env):
    """
    Return environment image version.
    If the environment is running, get image version from the container tag.
    Otherwise, get image version from the configuration.
    """

    try:
        container = env.get_container()
    except errors.EnvironmentNotRunningError:
        logging.debug(
            constants.IMAGE_VERSION_CONTAINER_MISSING.format(env_name=env.name)
        )
        return env.image_version
    if not container.image.tags:
        LOG.warning(
            constants.IMAGE_VERSION_TAG_MISSING.format(env_name=env.name)
        )
        return env.image_version
    tag = container.image.tags[0]
    image_tag = tag.split(":")[-1]
    airflow_v, composer_v = utils.get_airflow_composer_versions(image_tag)
    airflow_v = utils.format_airflow_version_dotted(airflow_v)
    return utils.get_image_version_tag(airflow_v, composer_v)


def get_environments_status(
    envs: List[pathlib.Path],
) -> List[EnvironmentStatus]:
    """Get list of environment statuses."""
    environments_status = []
    for env_path in envs:
        try:
            env = Environment.load_from_config(env_path, None)
            env_status = env.status()
            image_version = get_image_version(env)
        except errors.InvalidConfigurationError:
            env_status = "Could not parse the config"
            image_version = "x"
        environment_status = EnvironmentStatus(
            env_path.name, image_version, env_status
        )
        environments_status.append(environment_status)
    return environments_status


class EnvironmentConfig:
    def __init__(self, env_dir_path: pathlib.Path, port: Optional[int]):
        self.env_dir_path = env_dir_path
        self.config = self.load_configuration_from_file()
        self.project_id = self.get_str_param("composer_project_id")
        self.image_version = self.get_str_param("composer_image_version")
        self.location = self.get_str_param("composer_location")
        self.dags_path = self.get_str_param("dags_path")
        self.dag_dir_list_interval = self.parse_int_param(
            "dag_dir_list_interval", allowed_range=(0,)
        )
        self.port = (
            port
            if port is not None
            else self.parse_int_param("port", allowed_range=(0, 65536))
        )

    def load_configuration_from_file(self) -> Dict:
        """
        Load environment configuration from json file.

        Returns:
            Dict:
                Environment configuration dictionary.
        """
        config_path = self.env_dir_path / "config.json"
        LOG.info("Loading configuration file from %s", config_path)
        if not config_path.is_file():
            raise errors.ComposerCliError(
                f"Configuration file '{config_path}' not found."
            )
        with open(config_path) as fp:
            try:
                config = json.load(fp)
            except json.JSONDecodeError as err:
                raise errors.FailedToParseConfigError(config_path, err)
        return config

    def get_str_param(self, name: str):
        """
        Get parameter from the config. Raises an error if the parameter does
        not exist in the config.
        """
        try:
            return self.config[name]
        except KeyError:
            raise errors.MissingRequiredParameterError(name) from None

    def parse_int_param(
        self,
        name: str,
        allowed_range: Optional[Tuple[int, int]] = None,
    ):
        """
        Get parameter from the config and convert it to integer.
        Raises an error if the parameter value is not a valid integer.
        Optional ``allowed_range`` argument can be used to validate if
        parameter value is in the given range.

        Args:
            name: Name of the parameter in the config
            allowed_range: Tuple containing allowed range of values

        Returns:
            Parameter value converted to integer
        """
        try:
            value = self.get_str_param(name)
            value = int(value)
        except ValueError as err:
            raise errors.FailedToParseConfigParamIntError(name, value) from None
        if allowed_range is None:
            return value
        if value < allowed_range[0] or (
            len(allowed_range) > 1 and value > allowed_range[1]
        ):
            raise errors.FailedToParseConfigParamIntRangeError(
                name, value, allowed_range
            )
        return value


class Environment:
    def __init__(
        self,
        env_dir_path: pathlib.Path,
        project_id: str,
        image_version: str,
        location: str,
        dags_path: Optional[str],
        dag_dir_list_interval: int = 10,
        port: Optional[int] = None,
        pypi_packages: Optional[Dict] = None,
        environment_vars: Optional[Dict] = None,
    ):
        self.name = env_dir_path.name
        self.container_name = f"{constants.CONTAINER_NAME}-{self.name}"
        self.env_dir_path = env_dir_path
        self.airflow_db = self.env_dir_path / "airflow.db"
        self.entrypoint_file = DOCKER_FILES / "entrypoint.sh"
        self.requirements_file = self.env_dir_path / "requirements.txt"
        self.project_id = project_id
        self.image_version = image_version
        self.image_tag = get_docker_image_tag_from_image_version(image_version)
        self.location = location
        self.dags_path = files.resolve_dags_path(dags_path, env_dir_path)
        self.dag_dir_list_interval = dag_dir_list_interval
        self.port: int = port if port is not None else 8080
        self.pypi_packages = (
            pypi_packages if pypi_packages is not None else dict()
        )
        self.environment_vars = (
            environment_vars if environment_vars is not None else dict()
        )
        self.docker_client = self.get_client()

    def get_client(self):
        try:
            return docker.from_env()
        except docker.errors.DockerException as err:
            logging.debug("Docker not found.", exc_info=True)
            raise errors.DockerNotAvailableError(err) from None

    def get_container(
        self, assert_running: bool = False, ignore_not_found: bool = False
    ):
        """
        Returns created docker container and raises when it's not created.

        Args:
            assert_running: assert that container is running
        """
        try:
            container = self.docker_client.containers.get(self.container_name)
            if (
                assert_running
                and container.status != constants.ContainerStatus.RUNNING
            ):
                raise errors.EnvironmentNotRunningError() from None
            return container
        except docker_errors.NotFound:
            logging.debug("Container not found.", exc_info=True)
            if not ignore_not_found:
                raise errors.EnvironmentNotFoundError() from None

    @classmethod
    def load_from_config(cls, env_dir_path: pathlib.Path, port: Optional[int]):
        """Create local environment using 'config.json' configuration file."""
        config = EnvironmentConfig(env_dir_path, port)
        environment_vars = load_environment_variables(env_dir_path)

        return cls(
            env_dir_path=env_dir_path,
            project_id=config.project_id,
            image_version=config.image_version,
            location=config.location,
            dags_path=config.dags_path,
            dag_dir_list_interval=config.dag_dir_list_interval,
            port=config.port,
            environment_vars=environment_vars,
        )

    @classmethod
    def from_source_environment(
        cls,
        source_environment: str,
        project: str,
        location: str,
        env_dir_path: pathlib.Path,
        web_server_port: Optional[int],
        dags_path: Optional[str],
    ):
        """
        Create Environment using configuration retrieved from Composer
        environment.
        """
        software_config = get_software_config_from_environment(
            project, location, source_environment
        )

        pypi_packages = {k: v for k, v in software_config.pypi_packages.items()}
        env_variables = get_env_variables(software_config)
        airflow_overrides = get_airflow_overrides(software_config)
        env_variables.update(airflow_overrides)
        env_variables = filter_not_modifiable_env_vars(env_variables)

        return cls(
            env_dir_path=env_dir_path,
            project_id=project,
            image_version=software_config.image_version,
            location=location,
            dags_path=dags_path,
            dag_dir_list_interval=10,
            port=web_server_port,
            pypi_packages=pypi_packages,
            environment_vars=env_variables,
        )

    def pypi_packages_to_requirements(self):
        """Create requirements file using environment PyPi packagest list."""
        reqs = sorted(
            f"{key}{value}" for key, value in self.pypi_packages.items()
        )
        reqs_lines = "\n".join(reqs)
        with open(self.env_dir_path / "requirements.txt", "w") as fp:
            fp.write(reqs_lines)

    def environment_vars_to_env_file(self):
        """
        Write fetched environment variables keys to `variables.env` file.
        """
        env_vars = sorted(
            f"# {key}=" for key, _ in self.environment_vars.items()
        )
        env_vars_lines = "\n".join(env_vars)
        with open(self.env_dir_path / "variables.env", "w") as fp:
            fp.write(env_vars_lines)

    def assert_requirements_exist(self):
        """Asserts that PyPi requirements file exist in environment directory."""
        req_file = self.env_dir_path / "requirements.txt"
        if not req_file.is_file():
            raise errors.ComposerCliError(f"Missing '{req_file}' file.")

    def write_environment_config_to_config_file(self):
        """Saves environment configuration to config.json file."""
        config = {
            "composer_image_version": self.image_version,
            "composer_location": self.location,
            "composer_project_id": self.project_id,
            "dags_path": self.dags_path,
            "dag_dir_list_interval": int(self.dag_dir_list_interval),
            "port": int(self.port),
        }
        with open(self.env_dir_path / "config.json", "w") as fp:
            json.dump(config, fp, indent=4)

    def create_docker_container(self):
        """Creates docker container.

        Raises when docker container with the same name already exists.
        """
        LOG.debug("Creating container")
        mounts = get_image_mounts(
            self.env_dir_path,
            self.dags_path,
            utils.resolve_gcloud_config_path(),
            self.requirements_file,
        )
        default_vars = get_default_environment_variables(
            self.dag_dir_list_interval, self.project_id
        )
        env_vars = {**default_vars, **self.environment_vars}

        if platform.system() == "Windows" and env_vars["COMPOSER_CONTAINER_RUN_AS_HOST_USER"] == "True":
          raise Exception("COMPOSER_CONTAINER_RUN_AS_HOST_USER must be set to `False` on Windows")

        ports = {
            f"8080/tcp": self.port,
        }
        entrypoint = f"sh {constants.ENTRYPOINT_PATH}"
        memory_limit = constants.DOCKER_CONTAINER_MEMORY_LIMIT

        def create_container():
            try:
                return self.docker_client.containers.create(
                    self.image_tag,
                    name=self.container_name,
                    entrypoint=entrypoint,
                    environment=env_vars,
                    mounts=mounts,
                    ports=ports,
                    mem_limit=memory_limit,
                    detach=True,
                )
            except docker_errors.APIError as err:
                logging.debug(
                    "Received docker API error when creating container.",
                    exc_info=True,
                )
                if err.status_code == constants.CONFLICT_ERROR_CODE:
                    raise errors.EnvironmentAlreadyRunningError(
                        self.name
                    ) from None
                raise

        try:
            container = create_container()
        except docker_errors.ImageNotFound:
            LOG.debug(
                "Failed to create container with ImageNotFound error. "
                "Pulling the imagae..."
            )
            self.pull_image()
            container = create_container()
        except docker_errors.APIError as err:
            error = f"Failed to create container with an error: {err}"
            if is_mount_permission_error(err):
                error += constants.DOCKER_PERMISSION_ERROR_HINT.format(
                    docs_faq_url=constants.COMPOSER_FAQ_MOUNTING_LINK
                )
            raise errors.EnvironmentStartError(error)
        copy_entrypoint_to_container(container, self.entrypoint_file)
        return container

    def pull_image(self):
        """Pull Composer docker image."""
        try:
            # TODO: (b/237054183): Print detailed status (progress bar of image pulling)
            with console.get_console().status(constants.PULL_IMAGE_MSG):
                self.docker_client.images.pull(self.image_tag)
        except (docker_errors.ImageNotFound, docker_errors.APIError):
            logging.debug("Failed to pull composer image.", exc_info=True)
            raise errors.ImageNotFoundError(self.image_version) from None

    def create(self):
        """Creates Composer local environment.

        Directory with environment name will be created under `composer` path
        and environment configuration will be saved to config.json and
        requirements.txt files.
        """
        assert_image_exists(self.image_version)
        files.create_environment_directories(self.env_dir_path, self.dags_path)
        files.create_empty_file(self.airflow_db, skip_if_exist=False)
        self.write_environment_config_to_config_file()
        self.pypi_packages_to_requirements()
        self.environment_vars_to_env_file()
        console.get_console().print(
            constants.CREATE_MESSAGE.format(
                env_dir=self.env_dir_path,
                env_name=self.name,
                config_path=self.env_dir_path / "config.json",
                requirements_path=self.env_dir_path / "requirements.txt",
                env_variables_path=self.env_dir_path / "variables.env",
                dags_path=self.dags_path,
            )
        )

    def assert_container_is_active(self):
        """
        Asserts docker container is in running or created state (is active).
        """
        status = self.get_container().status
        if status not in (
            constants.ContainerStatus.RUNNING,
            constants.ContainerStatus.CREATED,
        ):
            raise errors.EnvironmentStartError()

    def wait_for_start(self):
        """
        Poll environment logs to see if it is ready.
        When Airflow scheduler starts, it prints 'searching for files' in the
        logs. We are using it as marker of the environment readiness.
        """
        start_time = time.time()
        with console.get_console().status(
            "[bold green]Starting environment..."
        ):
            self.assert_container_is_active()
            for line in self.get_container().logs(stream=True, timestamps=True):
                line = line.decode("utf-8").strip()
                console.get_console().print(line)
                # TODO: (b/234684803) Improve detecting container readiness
                if "Searching for files" in line:
                    start_duration = time.time() - start_time
                    LOG.info(
                        "Environment started in %.2f seconds", start_duration
                    )
                    return
                if timeout_occurred(start_time):
                    raise errors.EnvironmentStartTimeoutError()
                self.assert_container_is_active()
        raise errors.EnvironmentStartError()

    def get_or_create_container(self):
        """
        Get existing container or create new container if it does not exist.
        """
        try:
            return self.get_container()
        except errors.EnvironmentNotRunningError:
            return self.create_docker_container()

    def start(self, assert_not_running=True):
        """Starts local composer environment.

        Before starting we are asserting that are required files in the
        environment directory. The docker container is created and started.
        This operation will raise an error if we are trying to use port that
        is already allocated.
        Started environment is polled until Airflow scheduler starts.
        """
        assert_image_exists(self.image_version)
        self.assert_requirements_exist()
        files.assert_dag_path_exists(self.dags_path)
        files.create_empty_file(self.airflow_db)
        files.fix_file_permissions(
            self.entrypoint_file, self.requirements_file, self.airflow_db
        )
        files.fix_line_endings(self.entrypoint_file, self.requirements_file)
        container = self.get_or_create_container()
        if (
            assert_not_running
            and container.status == constants.ContainerStatus.RUNNING
        ):
            raise errors.EnvironmentAlreadyRunningError(self.name) from None
        try:
            container.start()
        except docker.errors.APIError as err:
            logging.debug(
                "Starting environment failed with Docker API error.",
                exc_info=True,
            )
            # TODO: (b/234552960) Test on different OS/language setting
            if (
                err.status_code == constants.SERVER_ERROR_CODE
                and "port is already allocated" in str(err)
            ):
                container.remove()
                raise errors.ComposerCliError(
                    constants.PORT_IN_USE_ERROR.format(port=self.port)
                )
            error = f"Environment failed to start with an error: {err}"
            raise errors.EnvironmentStartError(error) from None
        self.wait_for_start()
        self.print_start_message()

    def print_start_message(self):
        """Print the start message after the environment is up and ready."""
        console.get_console().print(
            constants.START_MESSAGE.format(
                env_name=self.name,
                dags_path=self.dags_path,
                port=self.port,
            )
        )

    def logs(self, follow, max_lines):
        """
        Fetch and print logs from the running composer local environment.

        Container `logs` method returns blocking generator if follow is True,
        and byte-decoded string if follow is False. That's why we need two
        methods of handling and decoding logs.
        """
        log_lines = self.get_container().logs(
            timestamps=True,
            stream=follow,
            follow=follow,
            tail=max_lines,
        )
        if follow:
            LOG.debug(
                "Printing previous %s lines and following output "
                "from the container logs:",
                max_lines,
            )
            for line in log_lines:
                line = line.decode("utf-8").strip()
                console.get_console().print(line)
        else:
            LOG.debug(
                "Printing previous %s lines from container logs:", max_lines
            )
            log_lines = log_lines.decode("utf-8")
            for line in log_lines.split("\n"):
                console.get_console().print(line)

    def stop(self, remove_container=False):
        """
        Stops the local composer environment.

        By default container is not removed.
        """
        with console.get_console().status(
            f"[bold green]Stopping composer local environment..."
        ):
            container = self.get_container()
            container.stop()
            if remove_container:
                container.remove()

    def restart(self):
        """
        Restarts the local composer environment.

        This operation will stop and remove container if it is running.
        Then it will start it again.
        """
        try:
            self.stop(remove_container=True)
        except errors.EnvironmentNotRunningError:
            pass
        self.start(assert_not_running=False)

    def status(self) -> str:
        """Get status of the local composer environment."""
        try:
            return self.get_container().status
        except errors.EnvironmentNotRunningError:
            return "Not started"

    def run_airflow_command(self, command: List) -> None:
        """
        Run command list in the environment container.
        The commands are prefixed with `airflow`.
        """
        container = self.get_container(assert_running=True)
        command.insert(0, "airflow")
        result = container.exec_run(cmd=command)
        console.get_console().print(result.output.decode())

    def get_host_port(self) -> int:
        """
        Return port of the running environment. If it fails to retrieve it,
        return port from the environment configuration.
        """
        try:
            return self.get_container().ports["8080/tcp"][0]["HostPort"]
        except (IndexError, KeyError):
            LOG.info(constants.FAILED_TO_GET_DOCKER_PORT_WARN)
            return self.port

    def prepare_env_description(self, env_status: str) -> str:
        """Prepare description of the local composer environment."""
        if env_status == constants.ContainerStatus.RUNNING:
            port = self.get_host_port()
            web_url = constants.WEBSERVER_URL_MESSAGE.format(port=port)
        else:
            web_url = ""
        env_status = utils.wrap_status_in_color(env_status)

        return constants.DESCRIBE_ENV_MESSAGE.format(
            name=self.name,
            state=env_status,
            web_url=web_url,
            image_version=self.image_version,
            dags_path=self.dags_path,
            gcloud_path=utils.resolve_gcloud_config_path(),
        )

    def describe(self) -> None:
        """Describe the local composer environment."""
        env_status = self.status()
        desc = self.prepare_env_description(env_status)
        console.get_console().print(desc)
