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
import pytest

from tests.e2e import assert_dir_empty, run_app


@pytest.mark.e2e
def test_create_with_invalid_port(
    composer_image_version, valid_project_id, env_name, temporary_work_dir
):
    invalid_port_err = (
        "Invalid value for '--web-server-port' / '--port':"
        " -1 is not in the range 0<=x<=65536."
    )
    run_app(
        f"create --from-image-version {composer_image_version} --port -1 {valid_project_id} {env_name}",
        exit_code=2,
        expected_output=invalid_port_err,
    )
    assert_dir_empty(temporary_work_dir)
