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


ENTRYPOINT = (
    pathlib.Path(__file__).parents[2]
    / "composer_local_dev"
    / "docker_files"
    / "entrypoint.sh"
)


def _write_executable(path: pathlib.Path, contents: str) -> None:
    path.write_text(textwrap.dedent(contents), encoding="utf-8")
    path.chmod(0o755)


def test_install_airflow_deps_writes_requirements_as_run_user(tmp_path):
    command_log = tmp_path / "commands.log"
    run_as_user = tmp_path / "run_as_user.sh"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

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

    (tmp_path / "composer_requirements.txt").write_text(
        "requests==2.32.0\n", encoding="utf-8"
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
