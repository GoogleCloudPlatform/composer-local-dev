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
import re
import shutil
from unittest import mock

import pytest

from composer_local_dev import constants, errors, files

TEST_DATA_DIR = pathlib.Path(__file__).parent.parent / "test_data"


def clean_cli_output(output: str) -> str:
    """
    Remove pretty-print formatting (such as rectangle around the message) from
    the string output.
    """
    return output.replace("│", "").replace("\n", "").replace(" ", "")


@contextlib.contextmanager
def working_directory(path):
    """Changes working directory and returns to previous on exit"""
    prev_cwd = pathlib.Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)


class TestResolveEnvironment:
    @pytest.mark.parametrize("env_name", [None, "test"])
    def test_no_composer_dir(self, env_name):
        env_dir = (TEST_DATA_DIR / "missing_composer").resolve()
        exp_error = (
            constants.ENVIRONMENT_DIR_NOT_FOUND_ERROR.format(
                env_dir=(env_dir / "composer"),
                create_help=constants.CREATE_MESSAGE_HINT,
            )
            + constants.ADD_DEBUG_ON_ERROR_INFO
        )
        with pytest.raises(errors.ComposerCliError) as err, working_directory(
            env_dir
        ):
            files.resolve_environment_path(env_name)
            assert str(err) == exp_error

    @pytest.mark.parametrize("env_name", [None, "test"])
    def test_no_envs(self, env_name):
        env_dir = (TEST_DATA_DIR / "no_envs").resolve()
        exp_error = (
            constants.ENVIRONMENT_DIR_EMPTY_ERROR.format(
                env_dir=(env_dir / "composer"),
                create_help=constants.CREATE_MESSAGE_HINT,
            )
            + constants.ADD_DEBUG_ON_ERROR_INFO
        )
        with pytest.raises(errors.ComposerCliError) as err, working_directory(
            env_dir
        ):
            files.resolve_environment_path(env_name)
            assert str(err) == exp_error

    @pytest.mark.parametrize("env_name", ["one_env", "two_envs"])
    def test_not_exising_name(self, env_name):
        env_dir = (TEST_DATA_DIR / env_name).resolve()
        invalid_env = "invalid"
        env_path = env_dir / "composer" / invalid_env
        exp_error = (
            constants.ENVIRONMENT_PATH_NOT_FOUND_ERROR.format(
                env_path=env_path, create_help=constants.CREATE_MESSAGE_HINT
            )
            + constants.ADD_DEBUG_ON_ERROR_INFO
        )
        with pytest.raises(errors.ComposerCliError) as err, working_directory(
            env_dir
        ):
            files.resolve_environment_path(invalid_env)
            assert str(err) == exp_error

    @pytest.mark.parametrize("env_name", [None, "example_env"])
    def test_one_env_existing_name(self, env_name):
        env_dir = (TEST_DATA_DIR / "one_env").resolve()
        with working_directory(env_dir):
            env_path = files.resolve_environment_path(env_name)
            assert env_path == env_dir / "composer" / "example_env"

    @pytest.mark.parametrize("env_name", ["1", "second_env"])
    def test_two_env_existing_name(self, env_name):
        env_dir = (TEST_DATA_DIR / "two_envs").resolve()
        with working_directory(env_dir):
            env_path = files.resolve_environment_path(env_name)
            assert env_path == env_dir / "composer" / env_name

    def test_two_envs_no_default(self):
        env_dir = (TEST_DATA_DIR / "two_envs").resolve()
        composer_dir = env_dir / "composer"
        env_names = "1\n    second_env"
        error_msg = constants.ENVIRONMENT_NOT_SELECTED_ERROR.format(
            env_dir=composer_dir, env_names=env_names
        )
        with pytest.raises(errors.ComposerCliError) as err, working_directory(
            env_dir
        ):
            files.resolve_environment_path(None)
            assert str(err) == error_msg


class TestGetEnvironmentDirectories:
    def test_no_composer_dir(self):
        env_dir = (TEST_DATA_DIR / "missing_composer").resolve()
        with working_directory(env_dir):
            envs = files.get_environment_directories()
        assert [] == envs

    def test_no_envs(self):
        env_dir = (TEST_DATA_DIR / "no_envs").resolve()
        with working_directory(env_dir):
            envs = files.get_environment_directories()
        assert [] == envs

    def test_two_envs(self):
        env_dir = (TEST_DATA_DIR / "two_envs").resolve()
        expected_envs = [
            env_dir / "composer" / "1",
            env_dir / "composer" / "second_env",
        ]
        with working_directory(env_dir):
            envs = files.get_environment_directories()
        assert expected_envs == sorted(envs)


class TestCreateEnvironmentDirectories:
    @pytest.fixture
    def temporary_env_dir(self, tmp_path):
        yield tmp_path
        shutil.rmtree(tmp_path)

    def test_existing_dag_path(self, temporary_env_dir):
        env_dir = temporary_env_dir
        dags_path = env_dir / "dags"
        dags_path.mkdir()
        files.create_environment_directories(
            env_dir=env_dir, dags_path=dags_path
        )
        for path in (
            env_dir,
            env_dir / "dags",
            env_dir / "data",
            env_dir / "plugins",
        ):
            assert path.is_dir()

    def test_not_existing_dag_path(self, temporary_env_dir, capsys):
        env_dir = temporary_env_dir
        dags_path = env_dir / "dags"
        files.create_environment_directories(
            env_dir=env_dir, dags_path=dags_path
        )
        captured = capsys.readouterr()
        output = clean_cli_output(captured.out)
        expected_output = clean_cli_output(
            constants.CREATING_DAGS_PATH_WARN.format(dags_path=dags_path)
        )
        for path in (
            env_dir,
            env_dir / "dags",
            env_dir / "data",
            env_dir / "plugins",
        ):
            assert path.is_dir()
        assert expected_output == output


class TestResolveDagsPath:
    def test_optional_dags_path(self, tmpdir, capsys):
        env_dir = pathlib.Path(tmpdir)
        expected_dags_path = str(env_dir / "dags")
        dags_path = files.resolve_dags_path(None, env_dir)
        captured = capsys.readouterr()
        output = "".join(captured.out.split("\n"))
        assert expected_dags_path == dags_path
        assert constants.DAGS_PATH_NOT_PROVIDED_WARN in output

    def test_provided_dags_path(self, tmpdir):
        expected_dags_path = pathlib.Path(tmpdir) / "dags"
        expected_dags_path.mkdir(exist_ok=True)
        expected_dags_str_path = str(expected_dags_path)
        dags_path = files.resolve_dags_path(expected_dags_str_path, tmpdir)
        assert expected_dags_str_path == dags_path


class TestAssertDagsPathExists:
    def test_existing_path(self, tmp_path):
        files.assert_dag_path_exists(str(tmp_path))

    def test_missing_path(self):
        path = "i/dont/exist"
        error_msg = f"Dags path does not exist or is not a directory: {path}"
        with pytest.raises(errors.DAGPathNotExistError) as err:
            files.assert_dag_path_exists(path)
            assert str(err) == error_msg

    def test_path_is_file(self, tmp_path):
        file_path = tmp_path / "file.ext"
        with open(file_path, "w") as fp:
            pass
        error_msg = (
            f"Dags path does not exist or is not a directory: {file_path}"
        )
        with pytest.raises(errors.DAGPathNotExistError) as err:
            files.assert_dag_path_exists(str(file_path))
            assert str(err) == error_msg


def test_dos2unix_file(tmp_path):
    windows_string = b"file\r\nwith carriage returns\r\n"
    linux_string = b"file\nwith carriage returns\n"
    tmp_file = tmp_path / "tmp.txt"
    with open(tmp_file, "wb") as fp:
        fp.write(windows_string)
    files.dos2unix_file(tmp_file)
    with open(tmp_file, "rb") as fp:
        content = fp.read()
    assert content == linux_string
