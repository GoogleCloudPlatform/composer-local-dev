# Release notes

## 0.9.2

#### New:

- Adds triggerer support (started by default)
- Adds support for Python v3.11
- Removes support for Python v3.7
- Allow running container as host user to solve permission problems (#24)

#### Changes:

- Bumps google-auth package constraints

#### Fixes:

- Fix #11 - Cannot access data folder on local composer env (#29)

## 0.9.1

#### New:

- Adds `composer-dev remove` local environment command.

#### Changes:

- Aligns the paths for dags/plugins/data as requested in [issue #2](https://github.com/GoogleCloudPlatform/composer-local-dev/issues/2)

#### Fixes:

- Fixes package dependency requirements [issue #7](https://github.com/GoogleCloudPlatform/composer-local-dev/issues/7)
- Adds andling for Docker not having access to path where the CLI has been installed [(issue #1)](https://github.com/GoogleCloudPlatform/composer-local-dev/issues/1) and extends documentation.

## 0.9.0

Initial release
