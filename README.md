# Composer Local Development CLI tool

[Google Cloud Privacy Notice](https://cloud.google.com/terms/cloud-privacy-notice)

## Overview

Composer Local Development CLI tool streamlines Apache Airflow DAG development
for Cloud Composer 2 by running an Airflow environment locally. This local
Airflow environment uses an image of a specific Cloud Composer version.

You can create a local Airflow environments based on an existing Cloud Composer
environment. In this case, the local Airflow environment takes the list of
installed PyPI packages and environment variable names from your Cloud Composer
environment.

You can use this local Airflow environment for testing and development
purposes, such as to test new DAG code, PyPI packages, or Airflow configuration
options.

> **WARNING:** Use local Airflow environments **only for testing and
development purposes**. Cloud Composer does not support using locally
deployed Cloud Composer images for production purposes.

- Composer Local Development CLI tool supports only Cloud Composer 2 images.
    You can use any version of Cloud Composer 2 with Composer Local
    Development CLI tool.

- Composer Local Development CLI tool creates local Airflow environments in a
    directory where you run the `composer-dev create` command. To access your
    local Airflow environment later, run the tool commands in the path where
    you initially created the local environment. All data for the
    local environment is stored in a subdirectory at the path where you created
    the local environment: `./composer/<local_environment_name>`.

- Your computer must have enough disk space to store Cloud Composer
    images. Composer Local Development CLI tool stores one image file for each
    Cloud Composer version. For example, if you have two local
    Airflow environments with different Cloud Composer versions,
    Composer Local Development CLI tool stores two Cloud Composer
    images.

- Composer Local Development CLI tool uses colorized output. You can disable
    colorized output with the `NO_COLOR=1` variable:
    `NO_COLOR=1 composer-dev <other commands>`.

- If you have only one local environment, you can omit the local environment's
    name from all `composer-dev` commands, except the `run-airflow-cmd`.

- Once local environment started, the Airflow triggerer is up along with
    scheduler and webserver. Please note that Airflow CLI command
    `airflow triggerer` was released in Airflow 2.2.0 and thus won't
    work with older versions.

## Google Cloud documentation page

See [Google Cloud documentation][1] for more information about using Composer
Local Development CLI tool and Cloud Composer.

## Prerequisites

In order to run the CLI tool, install the following prerequisites:

- Python 3.8-3.11 with `pip`
- [gcloud CLI][2]
- Docker

Docker must be installed and running in the local system. To verify that
Docker is running, you can run any Docker CLI command, such as `docker ps`.

## Configure credentials

If not already done,
[get new user credentials to use for Application Default Credentials][3]:

```bash
gcloud auth application-default login
```

Login in `gcloud` using your Google account:

```bash
gcloud auth login
```

All API calls done by the Composer Local Development CLI tool and DAGs are
executed from the account that you use in gcloud CLI. For
example, if a DAG in your local Airflow environment reads contents of a
Cloud Storage bucket, then this account must have permissions to
access the bucket. This is different from Cloud Composer environments, where an
environment's service account makes the calls.

## Install from the source code

1. Clone this repository
2. In the top-level directory of the cloned repository, run:

    ```bash
    pip install .
    ```

Depending on your `pip` configuration, the path at which the tool is installed
might not be in `PATH` variable. If this is the case, `pip` displays a warning
message. You can use information from this warning message to add this
directory to the `PATH` variable in your operating system.

## Create a local Airflow environment with a specific Cloud Composer version

To list available versions of Cloud Composer, run:

```bash
composer-dev list-available-versions --include-past-releases --limit 10
```

To create a local Airflow environment with default parameters, run:

```bash
composer-dev create \
  --from-image-version IMAGE_VERSION \
  LOCAL_ENVIRONMENT_NAME
```

Other parameters:

```bash
composer-dev create \
  --from-image-version IMAGE_VERSION \
  --project PROJECT_ID \
  --port WEB_SERVER_PORT \
  --dags-path LOCAL_DAGS_PATH \
  LOCAL_ENVIRONMENT_NAME
```

Replace:

- `IMAGE_VERSION` with the name of the Cloud Composer image.
- `PROJECT_ID` with the [Project ID][4].
- `WEB_SERVER_PORT` with the port that Airflow web server must listen at.
- `LOCAL_DAGS_PATH` with the path to a local directory where the DAG files are
    located.
- `LOCAL_ENVIRONMENT_NAME` with the name of this local Airflow environment.

Example:

```bash
composer-dev create \
  --from-image-version composer-2.0.29-airflow-2.2.5 \
  example-local-environment
```

## Create a local Airflow environment from a Cloud Composer environment

**Caution:** Composer Local Development CLI tool **does not produce a local
copy of your Cloud Composer environment**.

Only the following information is taken from a Cloud Composer
environment:

- [Image version][5] (versions of Cloud Composer and Airflow used in your
    environment).
- List of [custom PyPI packages][6] installed in your environment.
- Commented list of names of [environment variables][7] set in your environment.

    **Important:** Cloud Composer **does not copy the values** of
    environment variables. You can manually uncomment environment variables
    [in the configuration file](#configure-environment-variables) and set their
    values, as required.

Other information and configuration parameters from the environment, such as
DAG files, DAG run history, Airflow variables, and connections, are not copied
from your Composer environment.

To create a local Airflow environment from an existing
Cloud Composer environment:

```bash
composer-dev create LOCAL_ENVIRONMENT_NAME \
    --from-source-environment ENVIRONMENT_NAME \
    --location LOCATION \
    --project PROJECT_ID \
    --port WEB_SERVER_PORT \
    --dags-path LOCAL_DAGS_PATH
```

Replace:

- `LOCAL_ENVIRONMENT_NAME` with a name for the local Airflow environment.
- `ENVIRONMENT_NAME` with the name of the Cloud Composer environment.
- `LOCATION` with the region where the Cloud Composer environment is
    located.
- `PROJECT_ID` with the [Project ID][4].
- `WEB_SERVER_PORT` with a port for the local Airflow web server.
- `LOCAL_DAGS_PATH` with a path to a local directory where the DAGs are
    located.

Example:

```bash
composer-dev create example-local-environment \
  --from-source-environment example-environment \
  --location us-central1 \
  --project example-project \
  --port 8081 \
  --dags-path example_directory/dags
```

## Enable the container user to access mounted files and directories from the host

By default, the Composer container runs as the user `airflow` with UID 999. The user needs to have access the files and
directories mounted from the host, e.g., `~/.config/gcloud/application_default_credentials.json`.

Known issues:

- `google.auth.exceptions.DefaultCredentialsError: Your default credentials were not found`: it might be because you are
  running the container with the default user `airflow (999)` and the host directory `~/.config/gcloud/` is missing the
  execute permission for the user.
- `[Errno 13] Permission denied: '/home/airflow/.config/gcloud/application_default_credentials.json'`: it might be
  because you are running the container with the default user `airflow (999)` and the host file
  `~/.config/gcloud/application_default_credentials.json` is missing the read permission for the user.

On Linux or MacOS, it's recommended that you run the container as the current host user by adding
`COMPOSER_CONTAINER_RUN_AS_HOST_USER=True` in `composer/<LOCAL_ENVIRONMENT_NAME>/variables.env`. But the feature is not
available on Windows, so you might need to update the permissions of the mounted files and directories on the host to
allow access by the user inside of the container.

## Start a local Airflow environment

To start a local Airflow environment, run:

```bash
composer-dev start LOCAL_ENVIRONMENT_NAME
```

## Stop or restart a local Airflow environments

When you restart a local Airflow environment, Composer Local Development CLI
tool restarts the Docker container where the environment runs. All Airflow
components are stopped and started again. As a result, all DAG runs that are
executed during a restart are marked as failed.

To restart or start a stopped local Airflow environment, run:

```bash
composer-dev restart LOCAL_ENVIRONMENT_NAME
```

To stop a local Airflow environment, run:

```bash
composer-dev stop LOCAL_ENVIRONMENT_NAME
```

**Note:** The `stop` command does not [delete the local Airflow environment](#delete-a-local-airflow-environment).

## Add and update DAGs

Dags are stored in the directory that you specified in the `--dags-path`
parameter when you created your local Airflow environment. By default, this
directory is `./composer/<local_environment_name>/dags`. You can get the
directory used by your environment with the
[`describe` command](#get-a-list-and-status-of-local-airflow-environments).

To add and update DAGs, change files in this directory. You do not need to
restart your local Airflow environment.

## View local Airflow environment logs

You can view recent logs from a Docker container that runs your local Airflow
environment. In this way, you can monitor container-related events and check
Airflow logs for errors such as dependency conflicts caused by PyPI packages
installation.

**Note:** Composer Local Development CLI tool does not write DAG run and task
logs to files. You can view these logs in the Airflow UI of your local Airflow
environment.

To view logs from a Docker container that runs your local Airflow environment,
run:

```bash
composer-dev logs LOCAL_ENVIRONMENT_NAME --max-lines 10
```

To follow the log stream, omit the `--max-lines` argument:

```bash
composer-dev logs LOCAL_ENVIRONMENT_NAME
```

## Run an Airflow CLI command

You can run [Airflow CLI commands][8] in your local Airflow environment.

**Note:** The command syntax is different from
[gcloud CLI syntax for Airflow CLI commands][9].

To run an Airflow CLI command:

```bash
composer-dev run-airflow-cmd LOCAL_ENVIRONMENT_NAME \
  SUBCOMMAND SUBCOMMAND_ARGUMENTS
```

Example:

```bash
composer-dev run-airflow-cmd example-local-environment dags list -o table
```

## Configure local Airflow environments

Composer Local Development CLI tool takes configuration parameters for a local
Airflow environment from the local environment's directory
(`./composer/<local_environment_name>`).

Configuration is applied when a local Airflow environment is started. For
example, if you add conflicting PyPI package requirements, then Composer Local
Development CLI tool reports errors when you start the local environment.

**Important:** Composer Local Development CLI tool does not store the
`airflow.cfg` file in this directory. This file is located in the Docker image
of the environment. You can change Airflow configuration options by
[configuring environment variables](#configure-environment-variables).

### Get a list and status of local Airflow environments

To list all available local Airflow environments and display their status:

```bash
composer-dev list
```

To describe a specific environment, and get details such as image version, DAGs
path, and web server URL of an environment:

```bash
composer-dev describe LOCAL_ENVIRONMENT_NAME
```

### List images used by local Airflow environments

To list all images used by Composer Local Development CLI tool, run:

```bash
docker images --filter=reference='*/cloud-airflow-releaser/*/*'
```

### Install plugins and change data

Plugins and data for a local Airflow environment are taken from the
local environment's directory: `./composer/<local_environment_name>/data` and
`./composer/<local_environment_name>/plugins`).

To change the contents of `/data` and `/plugins` directories, add or remove
files in these directories. Docker automatically propagates file changes to
your local Airflow environment.

Composer Local Development CLI tool does not support specifying a different
directory for data and plugins.

### Configure environment variables

To configure environment variables, edit the `variables.env` file in the
environment directory:
`./composer/<local_environment_name>/variables.env`.

**Caution:** As a safety measure, values of environment variables **are not
copied** from your Cloud Composer environment, and the list of variable names
is commented. For example, you might want to specify different values so that
your DAGs do not interact with your production environments, or to omit setting
some of the variables.

The `variables.env` file must contain key-value definitions, one line for each
environment variable. To change Airflow configuration options, use the
`AIRFLOW__SECTION__KEY` format. For more information about the available
environment variables, see [Airflow configuration reference][10]

```bash
EXAMPLE_VARIABLE=True
ANOTHER_VARIABLE=test
AIRFLOW__WEBSERVER__DAG_DEFAULT_VIEW=graph
```

To apply the changes, [restart your local Airflow environment](#stop-or-restart-a-local-airflow-environments).

### Install or remove PyPI packages

To install or remove PyPI packages, modify the `requirements.txt` file in the
environment directory: `./composer/<local_environment_name>/requirements.txt`.

Requirements must follow the format specified in [PEP-508][12] where each
requirement is specified in lowercase and consists of the package name with
optional extras and version specifiers.

To apply the changes, [restart your local Airflow environment](#stop-or-restart-a-local-airflow-environments).

### Switch to a different Cloud Composer image

You can use any Cloud Composer 2 image with Composer Local Development CLI
tool and switch between the images. This approach is different from
[upgrading][11] your Cloud Composer environment, because configuration
parameters of your local Airflow environment are applied when it starts.

For example, after a new Cloud Composer version is released, you can switch
your environment to use the new version, and keep existing local Airflow
environment configuration. As another example, you can switch between
different Airflow versions within a specific Cloud Composer version.

To change the environment's image used by your local Airflow environment:

1. Edit the local environment configuration file:
    `./composer/<local_environment_name>/config.json`.

2. Change the value of the `composer_image_version` parameter. To view
    available values, you can
    [list available Cloud Composer versions](#create-a-local-airflow-environment-with-a-specific-cloud-composer-version).

3. To apply the changes, [restart your local Airflow environment](#stop-or-restart-a-local-airflow-environments).

### Delete a local Airflow environment

**Caution:** Make sure that you saved all required data from the environment,
such as logs and configuration.

To delete a local Airflow environment, run the following command:

```bash
composer-dev remove LOCAL_ENVIRONMENT_NAME
```

If the environment is running, add the `--force` flag to force its removal.

### Delete Docker images

To delete all images downloaded by Composer Local Development CLI tool, run:

```bash
docker rmi $(docker images --filter=reference='*/cloud-airflow-releaser/*/*' -q)
```

## Troubleshooting

This section provides solutions to common issues.

### Unable to start a local environment on MacOS X

If you installed the `composer-dev` package to a directory where Docker cannot
access it, then your local environment might not start.

For example, if Python is installed in the `/opt` directory, such as when you
install it with default Homebrew configuration on MacOS X, then the
`composer-dev` package is also installed in the `/opt` directory. Because
Docker complies with Apple's sandbox rules, the `/opt` directory isn't
available by default. In addition, you cannot add it through the UI (Settings >
Resources > File sharing).

In this case, Composer Local Development CLI tool generates the following
error message:

```none
Failed to create container with an error: 400 Client Error for ...
Bad Request ("invalid mount config for type "bind": bind source path does not exist:
/opt/homebrew/lib/python3.9/site-packages/composer_local_dev/docker_files/entrypoint.sh

Possible reason is that composer-dev was installed in the path that is
not available to Docker. See...")
```

You can use one of the following solutions:

- Install Python or the `composer-dev` package to a different directory, so
    that Docker can access the package.
- Manually edit the
    `~/Library/Group\ Containers/group.com.docker/settings.json` file and
    add `/opt` to `filesharingDirectories`.

---
[1]: https://cloud.google.com/composer/docs/composer-2/run-local-airflow-environments
[2]: https://cloud.google.com/sdk/docs/install
[3]: https://cloud.google.com/sdk/gcloud/reference/auth/application-default/login
[4]: https://cloud.google.com/resource-manager/docs/creating-managing-projects
[5]: https://cloud.google.com/composer/docs/concepts/versioning/composer-versions
[6]: https://cloud.google.com/composer/docs/composer-2/install-python-dependencies
[7]: https://cloud.google.com/composer/docs/composer-2/set-environment-variables
[8]: https://airflow.apache.org/docs/apache-airflow/stable/cli-and-env-variables-ref.html
[9]: https://cloud.google.com/composer/docs/composer-2/access-airflow-cli
[10]: https://airflow.apache.org/docs/apache-airflow/stable/configurations-ref.html
[11]: https://cloud.google.com/composer/docs/composer-2/upgrade-environments
[12]: https://www.python.org/dev/peps/pep-0508/#grammar
