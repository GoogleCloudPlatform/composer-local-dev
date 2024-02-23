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

from pathlib import Path

import nox

DEFAULT_PYTHON_VERSION = "3.9"
TEST_PYTHON_VERSIONS = ["3.8", "3.9", "3.10", "3.11"]

CURRENT_DIRECTORY = Path(__file__).parent.absolute()

nox.options.sessions = [
    "unit",
]


def install_tests_profile(session):
    session.install(".[tests]")


def install_docs_profile(session):
    session.install(".[docs]")


@nox.session(python=TEST_PYTHON_VERSIONS)
def unit(session):
    """Run the unit test suite."""
    install_tests_profile(session)

    session.run(
        "pytest",
        str(Path("tests/unit")),
        *session.posargs,
    )


@nox.session(python=TEST_PYTHON_VERSIONS)
def e2e(session):
    """Run the e2e test suite."""
    install_tests_profile(session)

    session.run(
        "pytest",
        "--e2e",
        str(Path("tests/e2e")),
        *session.posargs,
    )


@nox.session(python=TEST_PYTHON_VERSIONS)
def coverage(session):
    install_tests_profile(session)

    session.run(
        "coverage",
        "run",
        "-m",
        "pytest",
    )
    session.run(
        "coverage",
        "html",
    )


@nox.session(python=DEFAULT_PYTHON_VERSION)
def docs(session):
    install_docs_profile(session)
    session.run("sphinx-build", "-b", "html", "docs/source", "docs/_build/")
