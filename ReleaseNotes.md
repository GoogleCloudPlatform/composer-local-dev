# Release notes

## TODO

### New

- Support for Composer 3

## 0.9.4

### Fixes

- Fix `/home/airflow/run_as_user.sh: Permission denied` on Windows
- Fix support for Airflow <= 2.6 (#92)

## 0.9.3

### New

- Add LocalExecutor support as core executor
- Add PostgreSQL support (needed for LocalExecutor)
- Option to mount KUBECONFIG to easily support KubernetesPodOperator

### Changes

- Bump docker sdk constraints

### Fixes

- fix: keep ENV and PYTHONPATH when Composer is started as local user (#48)
- Fix container not restarting once stopped when started as local user (#49)
- Avoid SyntaxWarning by making IMAGE_VERSION_PATTERN a raw string (#73)
- fix: update file permission check to support Windows OS (#83)
- Change `airflow db init` to `airflow db migrate` in entrypoint script (#77)

## 0.9.2

### New

- Adds triggerer support (started by default)
- Adds support for Python v3.11
- Removes support for Python v3.7
- Allow running container as host user to solve permission problems (#24)

### Changes

- Bumps google-auth package constraints

### Fixes

- Fix #11 - Cannot access data folder on local composer env (#29)

## 0.9.1

### New

- Adds `composer-dev remove` local environment command.

### Changes

- Aligns the paths for dags/plugins/data as requested in [issue #2](https://github.com/GoogleCloudPlatform/composer-local-dev/issues/2)

### Fixes

- Fixes package dependency requirements [issue #7](https://github.com/GoogleCloudPlatform/composer-local-dev/issues/7)
- Adds handling for Docker not having access to path where the CLI has been installed
  [(issue #1)](https://github.com/GoogleCloudPlatform/composer-local-dev/issues/1) and extends documentation.

## 0.9.0

Initial release
