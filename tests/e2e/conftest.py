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

import os
import warnings

import pytest

from tests.e2e import run_cmd


def pytest_addoption(parser):
    parser.addoption(
        "--e2e", action="store_true", default=False, help="Run end to end tests"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: mark tests as end to end tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--e2e"):
        return
    skip_e2e = pytest.mark.skip(reason="Need --e2e option to run")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_e2e)


def get_env_var(name: str) -> str:
    if name not in os.environ:
        raise ValueError(
            f"Missing {name} in system environment variables. Configure it to run the E2E tests."
        )
    return os.environ[name]


@pytest.fixture(scope="session")
def composer_image_version_older() -> str:
    return "composer-2.0.8-airflow-2.2.3"


@pytest.fixture(scope="session")
def composer_image_version() -> str:
    try:
        return os.environ["COMPOSER_TESTS_IMAGE_VERSION"]
    except KeyError:
        default = "composer-2.0.24-airflow-2.2.5"
        warnings.warn(
            f"COMPOSER_TESTS_IMAGE_VERSION is not set. "
            f"Using default Composer image version: {default}"
        )
        return default


@pytest.fixture(scope="session")
def valid_project_id() -> str:
    return get_env_var("COMPOSER_TESTS_PROJECT_ID")


@pytest.fixture(scope="session")
def env_name() -> str:
    return "testenv"


@pytest.fixture(autouse=True)
def e2e_teardown():
    yield
    containers = run_cmd(
        "docker ps -a -q --filter=name=composer-local-dev-"
    ).stdout.strip()
    if not containers:
        print("No containers to remove.")
        return
    for container_id in containers.split():
        run_cmd(f"docker stop {container_id}")
        run_cmd(f"docker rm {container_id}")


@pytest.fixture(autouse=True)
def temporary_work_dir(tmp_path):
    """
    Change working directory to unique temporary path during the test.
    """
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        yield tmp_path
    finally:
        os.chdir(cwd)
