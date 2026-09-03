# Copyright 2026 Google LLC
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
import pathlib
import shlex
import subprocess
import textwrap

import pytest

ENTRYPOINT = (
    pathlib.Path(__file__).parents[2]
    / "composer_local_dev"
    / "docker_files"
    / "entrypoint.sh"
)


def _write_executable(path: pathlib.Path, contents: str) -> None:
    path.write_text(textwrap.dedent(contents), encoding="utf-8")
    path.chmod(0o755)


def _run_install_airflow_deps(tmp_path: pathlib.Path) -> pathlib.Path:
    command_log = tmp_path / "commands.log"
    run_as_user = tmp_path / "run_as_user.sh"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)

    _write_executable(
        run_as_user,
        f"""\
        #!/bin/sh
        printf 'run_as_user:%s\\n' "$*" >> {shlex.quote(str(command_log))}
        if [ "$1" = "airflow" ] && [ "$2" = "version" ]; then
          echo "2.10.5+composer"
          exit 0
        fi
        exec "$@"
        """,
    )
    _write_executable(
        bin_dir / "sudo",
        f"""\
        #!/bin/sh
        printf 'sudo:%s\\n' "$*" >> {shlex.quote(str(command_log))}
        exit 0
        """,
    )

    entrypoint = ENTRYPOINT.read_text(encoding="utf-8")
    function_defs = entrypoint.rsplit('\nmain "$@"', maxsplit=1)[0]
    script = "\n".join(
        [
            function_defs,
            f"run_as_user={shlex.quote(str(run_as_user))}",
            "install_airflow_deps",
        ]
    )

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    subprocess.run(["bash", "-c", script], cwd=tmp_path, env=env, check=True)
    return command_log


def test_install_airflow_deps_writes_requirements_as_run_user(tmp_path):
    (tmp_path / "composer_requirements.txt").write_text(
        "requests==2.32.0\n", encoding="utf-8"
    )

    command_log = _run_install_airflow_deps(tmp_path)

    assert (tmp_path / "requirements_with_airflow_version.txt").read_text(
        encoding="utf-8"
    ) == "requests==2.32.0\n\napache-airflow==2.10.5+composer\n"
    commands = command_log.read_text(encoding="utf-8").splitlines()
    assert (
        "run_as_user:cp composer_requirements.txt "
        "requirements_with_airflow_version.txt"
    ) in commands
    assert any(
        line.startswith("run_as_user:bash -c")
        and "requirements_with_airflow_version.txt" in line
        for line in commands
    )
    assert any("apache-airflow==2.10.5+composer" in line for line in commands)


@pytest.mark.parametrize(
    "setup_composer_requirements",
    [
        "non_existent",
        "empty",
    ],
)
def test_install_airflow_deps_noop_when_composer_requirements_empty_or_missing(
    tmp_path, setup_composer_requirements
):
    if setup_composer_requirements == "empty":
        (tmp_path / "composer_requirements.txt").touch()

    command_log = _run_install_airflow_deps(tmp_path)

    assert not (tmp_path / "requirements_with_airflow_version.txt").exists()
    assert not command_log.exists()


@pytest.mark.parametrize(
    "initial_content",
    [
        "",  # empty
        "stale-package==1.0.0\n",  # pre-existing stale content
    ],
)
def test_install_airflow_deps_overwrites_existing_requirements_with_airflow_version(
    tmp_path, initial_content
):
    (tmp_path / "composer_requirements.txt").write_text(
        "requests==2.32.0\n", encoding="utf-8"
    )
    reqs_with_version = tmp_path / "requirements_with_airflow_version.txt"
    reqs_with_version.write_text(initial_content, encoding="utf-8")

    command_log = _run_install_airflow_deps(tmp_path)

    assert (
        reqs_with_version.read_text(encoding="utf-8")
        == "requests==2.32.0\n\napache-airflow==2.10.5+composer\n"
    )
    commands = command_log.read_text(encoding="utf-8").splitlines()
    assert (
        "run_as_user:cp composer_requirements.txt "
        "requirements_with_airflow_version.txt"
    ) in commands
