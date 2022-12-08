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

import pytest

from tests.e2e import assert_example_dag_listed, run_app


@pytest.mark.e2e
def test_full_run(composer_image_version, valid_project_id, env_name):
    dags_dir = pathlib.Path(__file__).parent / "example_dag"
    run_app(
        f"create --from-image-version {composer_image_version} "
        f"-p {valid_project_id} --dags-path {dags_dir} {env_name}"
    )
    run_app(f"start {env_name}")
    assert_example_dag_listed()
    run_app(f"stop {env_name}")
