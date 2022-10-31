 .. Copyright 2022 Google LLC

 .. Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

 ..   http://www.apache.org/licenses/LICENSE-2.0

 .. Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

Contributing
===============

Configure pre-commits
----------------------
Install Composer with the 'dev' profile to include pre-commit dependency::

    pip install .[dev]

Install hooks by running in the project root::

    pre-commit install

Pre-commit hooks will run on every commit on modified files. If you want to
run them manually run::

    pre-commit run --all-files

If you need to commit changes without running precommit add ``--no-verify`` flag::

    git commit --no-verify

Nox
----
For running our tests, calculating test coverage and building documentation we
are using ``nox``. It is included in ``tests` setup profile. To install it run::

    pip install composer-dev[tests]

To install it from the source code, run in the project root::

    pip install -e .[tests]

Documentation
-----------------
We're using ``sphinx`` for our documentation. You can access and modify documentation
source files in ``docs/source`` directory. To build the documentation run::

    nox -s docs
