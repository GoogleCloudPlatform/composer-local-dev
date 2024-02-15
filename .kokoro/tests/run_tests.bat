@rem  Copyright 2022 Google LLC
@rem
@rem  Licensed under the Apache License, Version 2.0 (the "License");
@rem  you may not use this file except in compliance with the License.
@rem  You may obtain a copy of the License at
@rem
@rem      http://www.apache.org/licenses/LICENSE-2.0
@rem
@rem  Unless required by applicable law or agreed to in writing, software
@rem  distributed under the License is distributed on an "AS IS" BASIS,
@rem  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
@rem  See the License for the specific language governing permissions and
@rem  limitations under the License.

@echo "Install pyenv tool for installing multiple Pythons"
call C:\Python37\python.exe -m pip install pyenv-win --target %USERPROFILE%\.pyenv
set "PYENV=%USERPROFILE%\.pyenv\pyenv-win\"
set "PYENV_ROOT=%USERPROFILE%\.pyenv\pyenv-win\"
set "PYENV_HOME=%USERPROFILE%\.pyenv\pyenv-win\"
set "PATH=%USERPROFILE%\.pyenv\pyenv-win\bin;%USERPROFILE%\.pyenv\pyenv-win\shims;%PATH%"

@echo "Install additional Python versions"
call %USERPROFILE%\.pyenv\pyenv-win\bin\pyenv install --skip-existing --register 3.8.10 3.9.13 3.10.5 3.11.5
call %USERPROFILE%\.pyenv\pyenv-win\bin\pyenv global 3.8.10 3.9.13 3.10.5 3.11.5

if defined KOKORO_BUILD_ID ( @rem export vars only for Kokoro job
  @rem  Setup service account credentials
  set "GOOGLE_APPLICATION_CREDENTIALS=%KOKORO_GFILE_DIR%/kokoro/service-account-key.json"

  @rem Setup project id
  set /p PROJECT_ID=<%KOKORO_GFILE_DIR%/kokoro/project-id.txt
  set COMPOSER_TESTS_PROJECT_ID=PROJECT_ID
)

@rem  install nox for testing
call C:\Python37\python.exe -m pip install --require-hashes --upgrade --quiet -r .kokoro/tests/requirements.txt
call C:\Python37\python.exe -m nox --version

@echo "******************** Running unit tests... ********************\n"
call C:\Python37\python.exe -m nox -s "unit"
@echo "******************** Unit tests complete.  ********************\n"
@echo "******************** Running E2E tests... ********************\n"
@rem call C:\C:\Python37\python.exe\python.exe -m nox -s "e2e"
@echo "******************** Tests complete.  ********************\n"
