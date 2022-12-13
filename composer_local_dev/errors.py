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

import functools
from typing import Optional, Tuple

import click
from google.auth import exceptions as auth_exception

from composer_local_dev import constants


class ComposerCliError(click.ClickException):
    """
    An exception that occurred in Composer CLI and can be handled and shown to
    the user.
    """

    def __init__(self, msg):
        msg += constants.ADD_DEBUG_ON_ERROR_INFO
        super().__init__(msg)


class ComposerCliFatalError(Exception):
    """
    Fatal exception that occurred in Composer CLI indicating unrecoverable
    state.
    """

    pass


class ImageNotFoundError(ComposerCliError):
    """Composer image not found."""

    def __init__(self, image_version):
        msg = constants.IMAGE_TAG_DOES_NOT_EXIST_ERROR.format(
            image_tag=image_version
        )
        super().__init__(msg)


class EnvironmentAlreadyRunningError(ComposerCliError):
    """Environment with the same name is already running."""

    def __init__(self, name):
        msg = constants.ENVIRONMENT_ALREADY_RUNNING.format(name=name)
        super().__init__(msg)


class EnvironmentNotRunningError(ComposerCliError):
    """Composer environment is not running."""

    def __init__(self):
        msg = constants.ENV_NOT_RUNNING
        super().__init__(msg)


class EnvironmentNotFoundError(EnvironmentNotRunningError):
    """Composer environment docker container was not found."""

    pass


class EnvironmentStartError(ComposerCliError):
    """Composer environment failed to start."""

    def __init__(self, msg: Optional[str] = None):
        if msg is None:
            msg = constants.ENVIRONMENT_FAILED_TO_START_ERROR
        super().__init__(msg)


class EnvironmentStartTimeoutError(EnvironmentStartError):
    """Composer environment start timed out."""

    def __init__(self):
        msg = constants.ENV_DID_NOT_START_TIMEOUT_ERROR.format(
            seconds=constants.OPERATION_TIMEOUT_SECONDS
        )
        super().__init__(msg)


class InvalidConfigurationError(ComposerCliError):
    """Composer environment configuration is not valid."""


class MissingRequiredParameterError(InvalidConfigurationError):
    """Missing required parameter in configuration file."""

    def __init__(self, param):
        msg = constants.MISSING_REQUIRED_PARAM_ERROR.format(param=param)
        super().__init__(msg)


class FailedToParseConfigParamIntError(InvalidConfigurationError):
    def __init__(self, param_name: str, value: str):
        msg = constants.INVALID_INT_VALUE_ERROR.format(
            param_name=param_name, value=value
        )
        super().__init__(msg)


class FailedToParseConfigParamIntRangeError(InvalidConfigurationError):
    def __init__(
        self,
        param_name: str,
        value: int,
        int_range: Tuple[
            int,
        ],
    ):
        if len(int_range) == 1:
            allowed_range = f"x>={int_range[0]}"
        else:
            allowed_range = f"{int_range[0]}<=x<={int_range[1]}"
        msg = constants.INVALID_INT_RANGE_VALUE_ERROR.format(
            param_name=param_name, value=value, allowed_range=allowed_range
        )
        super().__init__(msg)


class FailedToParseConfigError(InvalidConfigurationError):
    def __init__(self, config_path, err):
        msg = constants.INVALID_CONFIGURATION_FILE_ERROR.format(
            config_path=config_path, error=err
        )
        super().__init__(msg)


class FailedToParseVariablesError(InvalidConfigurationError):
    def __init__(self, env_file_path, invalid_line):
        msg = constants.INVALID_ENV_VARIABLES_FILE_ERROR.format(
            env_file_path=env_file_path, line=invalid_line
        )
        super().__init__(msg)


class DockerNotAvailableError(ComposerCliError):
    def __init__(self, err):
        super().__init__(constants.DOCKER_NOT_AVAILABLE_ERROR.format(error=err))


class InvalidAuthError(ComposerCliError):
    """Gcloud authentication is invalid or missing."""

    def __init__(self, err):
        error_str = str(err)
        # we are normalizing error, so it does not end up with two dots
        if error_str.endswith("."):
            error_str = error_str[:-1]
        super().__init__(constants.AUTH_INVALID_ERROR.format(error=error_str))


class DAGPathNotExistError(ComposerCliError):
    """DAG path does not exist or is not a directory."""

    def __init__(self, dags_path):
        super().__init__(
            constants.DAGS_PATH_NOT_EXISTS_ERROR.format(dags_path=dags_path)
        )


def catch_exceptions(func=None):
    """
    Catch exceptions and print user friendly message for common issues.
    """
    if not func:
        return functools.partial(catch_exceptions)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (
            click.ClickException,
            click.Abort,
        ):
            raise
        except auth_exception.DefaultCredentialsError as err:
            raise InvalidAuthError(str(err))
        except Exception:
            message = "\nFatal exception occurred. Please report at https://github.com/GoogleCloudPlatform/composer-local-dev/issues"
            raise ComposerCliFatalError(message)

    return wrapper
