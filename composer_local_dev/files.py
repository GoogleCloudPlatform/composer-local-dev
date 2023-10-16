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

import logging
import pathlib
import stat
from typing import List, Optional

from composer_local_dev import console, constants, errors, utils

LOG = logging.getLogger(__name__)


def resolve_environment_path(env_name: Optional[str]) -> pathlib.Path:
    """
    Provides and validates path to a given environment.
    Environments are defined in current working directory in ``composer``
    directory. If no environment name is given, path to single existing
    environment is returned, in case there is more than one environment
    defined it raises error.
    """
    env_dir = (pathlib.Path.cwd() / "composer").resolve()
    if not env_dir.is_dir():
        raise errors.ComposerCliError(
            constants.ENVIRONMENT_DIR_NOT_FOUND_ERROR.format(
                env_dir=env_dir, create_help=constants.CREATE_MESSAGE_HINT
            )
        )

    envs = get_available_environments(env_dir)
    LOG.info(
        "Found following local environments:\n    %s",
        "\n    ".join(str(env) for env in envs),
    )
    if not envs:
        raise errors.ComposerCliError(
            constants.ENVIRONMENT_DIR_EMPTY_ERROR.format(
                env_dir=env_dir, create_help=constants.CREATE_MESSAGE_HINT
            )
        )

    if env_name:
        LOG.info("Searching for provided local environment name: %s", env_name)
        env_path = env_dir / env_name
        if not env_path.is_dir():
            raise errors.ComposerCliError(
                constants.ENVIRONMENT_PATH_NOT_FOUND_ERROR.format(
                    env_path=env_path, create_help=constants.CREATE_MESSAGE_HINT
                )
            )
        return env_path
    else:
        if len(envs) > 1:
            env_names = sorted(str(env.name) for env in envs)
            env_names = "\n    ".join(env_names)
            raise errors.ComposerCliError(
                constants.ENVIRONMENT_NOT_SELECTED_ERROR.format(
                    env_dir=env_dir, env_names=env_names
                )
            )
        LOG.info(
            "Environment path not provided, defaulting to only "
            "existing environment path: %s",
            envs[0],
        )
        return envs[0]


def get_environment_directories() -> List[pathlib.Path]:
    """
    Finds and returns path to the environment directories available at the
    current working directory.
    If the composer directory does not exist, or it is empty, an empty list
    is returned.
    """
    env_dir = (pathlib.Path.cwd() / "composer").resolve()
    if not env_dir.is_dir():
        return []
    return get_available_environments(env_dir)


def resolve_dags_path(dags_path: Optional[str], env_dir: pathlib.Path) -> str:
    """
    Provides and validates path to the dags directory.
    If ``dags_path`` is None, the path is constructed from ``env_dir`` path and
    ``dags`` directory.
    If ``dags_path`` is not None, but it does not exist, a warning is raised.

    Returns absolute ``dags_path` path.
    """
    if dags_path is None:
        console.get_console().print(constants.DAGS_PATH_NOT_PROVIDED_WARN)
        dags_path = env_dir / "dags"
    else:
        dags_path = pathlib.Path(dags_path)
    return str(dags_path.resolve())


def create_environment_directories(env_dir: pathlib.Path, dags_path: str):
    """
    Create environment directories (overwriting existing ones).
    Environment directory is a directory which contains configuration files for
    composer local environment and files used by environment such as
    requirements.txt file, dags, data and plugins directories.
    """
    env_dirs = ("data", "plugins")
    LOG.info(
        "Creating environment directories %s in " "%s environment directory.",
        env_dirs,
        env_dir,
    )
    env_dir.mkdir(exist_ok=True, parents=True)
    for sub_dir in env_dirs:
        (env_dir / sub_dir).mkdir(exist_ok=True)
    dags_path = pathlib.Path(dags_path)
    if not dags_path.is_dir():
        console.get_console().print(
            constants.CREATING_DAGS_PATH_WARN.format(dags_path=dags_path)
        )
        dags_path.mkdir(parents=True)


def get_available_environments(composer_dir: pathlib.Path):
    """
    List local composer environments.
    Any directory with 'config.json' file placed directly under 'composer_dir'
    directory is considered to be an environment directory.
    """
    return [
        path
        for path in composer_dir.iterdir()
        if path.is_dir() and (path / "config.json").is_file()
    ]


def fix_file_permissions(
    entrypoint: pathlib.Path,
    requirements: pathlib.Path,
    airflow_db: pathlib.Path,
) -> None:
    """
    Fix file permissions for files used in Docker container when running under
    Linux OS. Windows and MAC OS X don't need it.
    Args:
        entrypoint: Init script of the container. It needs to be executable.
        requirements: List of PyPi packages to be installed in the container.
        It needs to be readable by all users.
        airflow_db: path to Airflow Sqlite database file.
        It needs to be writeable.
    """
    if not utils.is_linux_os():
        return
    make_file_readable_and_executable(entrypoint)
    make_file_writeable(requirements)
    make_file_writeable(airflow_db)


def make_file_readable_and_executable(file_path: pathlib.Path) -> None:
    file_path.chmod(0o0755)


def make_file_writeable(file_path: pathlib.Path) -> None:
    file_path.chmod(0o0666)


def fix_line_endings(
    entrypoint: pathlib.Path, requirements: pathlib.Path
) -> None:
    """
    Fix windows line endings so the files created under Windows
    can be used in the docker container.
    """
    dos2unix_file(entrypoint)
    dos2unix_file(requirements)


def dos2unix_file(path: pathlib.Path):
    """Replaces line endings in the file from DOS to UNIX format."""
    with open(path, "rb") as fp:
        content = fp.read()
    content = content.replace(b"\r\n", b"\n")
    with open(path, "wb") as fp:
        fp.write(content)


def create_empty_file(path: pathlib.Path, skip_if_exist: bool = True):
    """Create an empty file."""
    if skip_if_exist and path.exists():
        return
    with open(path, "w"):
        pass


def assert_dag_path_exists(path: str) -> None:
    """Raise an error if DAG path does not point to existing directory."""
    if pathlib.Path(path).is_dir():
        return
    raise errors.DAGPathNotExistError(path)
