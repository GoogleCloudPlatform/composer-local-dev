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

set -xe

# add user's pip binary path to PATH
export PATH="${HOME}/.local/bin:${PATH}"

if [[ ! -z "${KOKORO_BUILD_ID}" ]]; then # export vars only for Kokoro job
  # Setup service account credentials
  export GOOGLE_APPLICATION_CREDENTIALS=${KOKORO_GFILE_DIR}/kokoro/service-account-key.json

  # Setup project id
  export PROJECT_ID=$(cat "${KOKORO_GFILE_DIR}/kokoro/project-id.txt")
  export COMPOSER_TESTS_PROJECT_ID=PROJECT_ID
fi

if [[ "$OSTYPE" == "darwin"* ]]; then # Mac OSX
  # Mac requires .13 fix versions (which is not available for other platforms)
  pyenv install --skip-existing 3.8.10
  pyenv global 3.8.10
else
  pyenv install --skip-existing 3.8.10
  pyenv install --skip-existing 3.9.5
  pyenv install --skip-existing 3.11.5
  pyenv global 3.8.10 3.9.5 3.11.5
fi

# install nox for testing
python -m pip install --require-hashes --upgrade --quiet -r .kokoro/tests/requirements.txt
python -m nox --version

echo -e "******************** Running unit tests... ********************\n"
python -m nox -s "unit"
echo -e "******************** Unit tests complete.  ********************\n"
echo -e "******************** Running E2E tests... ********************\n"
if [[ "$OSTYPE" == "darwin"* ]]; then # Mac OSX
    echo "Skipping E2E tests on Mac OSX due to the missing Docker."  # TODO: (b/259378070) Install Docker on MacOS
else
    python -m nox -s "e2e"
fi
echo -e "******************** Tests complete.  ********************\n"
