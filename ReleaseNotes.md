# Release notes

## 0.10.2

### New

- Add extra_hosts section to access host machine from the composer container via `host.docker.internal`. Please refer to
"Interaction with other service on the host machine" in the README file.
- feat: Enable supplying and mounting plugins path (#70)

### Fixes

- use since in logs() when waiting for the env to start (#109)
- install python packages system-wide (#105)

### Changes

- relax google-auth constraints (#101)

## 0.10.1

### Fixes

- Variables got removed after restart on version 0.9.3 #95
- Postgres Data volume bind-mounted to wrong target location #98
- Fix sqlite persistence.

## 0.10.0

### New

- Support for Composer 3
- Make PostgreSQL the default `database`.

### Fixes

- composer-dev start fails - unable to start worker due to SQLAlchemy SQLite Uniqueness constraint errors (#88)
- Can't launch a Composer 3 image (#68)
- Fix `home/airflow/run_as_user.sh: Permission denied` On Windows (#94)

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
