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
import subprocess
import tempfile
import time
from typing import Optional

from click.testing import CliRunner

from composer_local_dev import cli


@contextlib.contextmanager
def temporary_work_dir(
    tmp_work_dir: Optional[pathlib.Path] = None,
) -> pathlib.Path:
    """
    Switch to tmp_work_dir temporary work directory. Creates the path if the
    tmp_work_dir does not exist or is None.

    Returns:
        tmp_work_dir
    """
    cwd = os.getcwd()
    if tmp_work_dir is None:
        tmp_work_dir = pathlib.Path(tempfile.mkdtemp())
    elif not tmp_work_dir.exists():
        tmp_work_dir.mkdir(parents=True)

    try:
        os.chdir(tmp_work_dir)
        yield tmp_work_dir
    finally:
        os.chdir(cwd)


def clean_cli_output(output: str) -> str:
    """
    Remove pretty-print formatting (such as rectangle around the message) from
    the string output.
    """
    reformatted = output.replace("│", "").replace("\n", " ")
    reformatted = " ".join(line for line in reformatted.split() if line.strip())
    return reformatted


def run_app(
    cmd: str,
    input: Optional[str] = None,
    exit_code: int = 0,
    expected_output: Optional[str] = None,
) -> object:
    """
    Wrapper method for running the CLI and asserting the exit code.
    Args:
        cmd: Command to run. Command is already prefixed with the tool name.
        input: The input to be passed to console if prompted by the tool.
        exit_code: Expected exit code.
        expected_output: The message expected to be in the console output.

    Returns:
        Result of the run.
    """
    print(f"Running E2E step: composer-dev {cmd}")
    cmd = cmd.split()
    runner = CliRunner()
    result = runner.invoke(cli.cli, cmd, input=input)
    if result.exit_code != exit_code:
        print(result.output)
        raise AssertionError(
            f"Expected exit code does not match actual: "
            f"{exit_code}!={result.exit_code}"
        )
    assert result.exit_code == exit_code
    if expected_output is not None:
        expected_output = clean_cli_output(expected_output)
        actual_output = clean_cli_output(result.output)
        if expected_output not in actual_output:
            raise AssertionError(
                f"Expected output not found in the actual output. "
                f"{expected_output} not in {actual_output}"
            )
        assert expected_output in actual_output
    return result


def assert_dir_empty(path: pathlib.Path):
    if any(path.iterdir()):
        raise AssertionError(f"Directory is not empty: {path}")


def assert_env_dir_created(work_dir: pathlib.Path, env_name: str):
    env_dir = work_dir / "composer" / env_name
    if not env_dir.exists():
        raise AssertionError(f"Environment directory does not exist: {env_dir}")
    config = env_dir / "config.json"
    assert config.exists()


def assert_example_dag_listed():
    for _ in range(60):
        time.sleep(1)
        result = run_app("run-airflow-cmd testenv dags list")
        if "example_dag | example_dag.py" in result.output:
            return
    else:
        raise AssertionError("Example DAG was not found")


def run_cmd(cmd: str):
    print(f"> {cmd}")
    result = subprocess.run(
        cmd.split(), capture_output=True, check=False, text=True
    )
    print(result.stdout)
    print(result.stderr)
    return result
