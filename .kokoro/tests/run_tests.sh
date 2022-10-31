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

set -e

# add user's pip binary path to PATH
export PATH="${HOME}/.local/bin:${PATH}"

if [[ "$OSTYPE" == "darwin"* ]]; then # Mac OSX
  # Mac requires .13 fix versions (which is not available for other platforms)
  pyenv install --skip-existing 3.7.13
  pyenv global 3.7.13
else
  pyenv install --skip-existing 3.7.10
  pyenv global 3.7.10
fi

# install nox for testing
python -m pip install --require-hashes --upgrade --quiet -r .kokoro/tests/requirements.txt
python -m nox --version

echo -e "******************** Running tests... ********************\n"
python -m nox -s "unit"
echo -e "******************** Tests complete.  ********************\n"
