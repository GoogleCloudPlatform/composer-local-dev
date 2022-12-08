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
import pathlib
import shutil

import pytest

from tests.e2e import run_app


@pytest.mark.e2e
def test_incompatible_deps(composer_image_version, valid_project_id, env_name):
    """
    Starting the composer environment should fail because requirements.txt file
    contains dependencies incompatible with each other.
    """
    # Create the environment
    run_app(
        f"create --from-image-version {composer_image_version} "
        f"-p {valid_project_id} {env_name}"
    )
    # Copy requirements.txt with incompatible dependencies to our environment
    requirements_src = (
        pathlib.Path(__file__).parent / "incompatible_requirements.txt"
    )
    requirements_dst = pathlib.Path(f"composer/{env_name}/requirements.txt")
    shutil.copyfile(str(requirements_src), str(requirements_dst))
    # Starting the environment should fail
    run_app(
        f"start {env_name}",
        exit_code=1,
        expected_output="Environment failed to start.",
    )
