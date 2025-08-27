#!/bin/bash

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

set -ex

readonly PRE_COMMIT_VERSION="4.2.0"

pyenv install --skip-existing 3.11.5
pyenv global 3.11.5
pip install pre-commit==$PRE_COMMIT_VERSION

git config --global --add safe.directory /tmpfs/src/git/composer-local-development
cd git/composer-local-development
FILES=$(git diff --diff-filter=AM --name-only HEAD~1 HEAD)
echo "Running pre-commit on the following files:"
echo "$FILES"
echo "$FILES" | xargs pre-commit run \
 --config=.pre-commit-config.yaml --show-diff-on-failure \
 --files