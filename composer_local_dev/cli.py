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

import logging
import pathlib
import shutil
from typing import List, Optional, Union

import rich.markdown
import rich_click as click

from composer_local_dev import console, constants
from composer_local_dev import environment as composer_environment
from composer_local_dev import errors, files, utils, version

LOG = logging.getLogger(__name__)

COMMON_OPTIONS = {
    "name": "Common options",
    "options": ["--verbose", "--debug", "--help"],
}
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.USE_MARKDOWN = True
click.rich_click.MAX_WIDTH = 130
click.rich_click.STYLE_HELPTEXT = ""
click.rich_click.OPTION_GROUPS = {
    "composer-dev create": [
        COMMON_OPTIONS,
        {
            "name": "From Composer source environment",
            "options": ["--from-source-environment", "--project", "--location"],
        },
        {
            "name": "From Composer image version",
            "options": ["--from-image-version"],
        },
        {
            "name": "Environment options",
            "options": ["--web-server-port", "--dags-path"],
        },
    ],
    "composer-dev start": [COMMON_OPTIONS],
    "composer-dev stop": [COMMON_OPTIONS],
    "composer-dev restart": [COMMON_OPTIONS],
    "composer-dev logs": [COMMON_OPTIONS],
    "composer-dev remove": [COMMON_OPTIONS],
    "composer-dev list_available_versions": [COMMON_OPTIONS],
    "composer-dev run_airflow_cmd": [COMMON_OPTIONS],
    "composer-dev describe": [COMMON_OPTIONS],
    "composer-dev list": [COMMON_OPTIONS],
}
click.rich_click.COMMAND_GROUPS = {
    "composer-dev": [
        {
            "name": "Running the environment",
            "commands": [
                "create",
                "start",
                "stop",
                "restart",
                "logs",
                "list",
                "describe",
                "remove",
            ],
        },
        {
            "name": "Other",
            "commands": [
                "run-airflow-cmd",
                "list-available-versions",
            ],
        },
    ]
}


def apply_cli_option_format(name):
    """Translate option_name to --option-name for help messages."""
    return f"--{name.replace('_', '-')}"


class MutuallyExclusiveOption(click.Option):
    def __init__(self, *args, **kwargs):
        self.mutual = kwargs.pop("mutual")
        option_names = ", ".join(
            apply_cli_option_format(name) for name in self.mutual
        )
        kwargs["help"] = (
            f"{kwargs.get('help', '')}. Option is mutually exclusive with "
            f"{option_names}."
        ).strip()
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        current_opt: bool = self.name in opts
        for mutex_opt in self.mutual:
            if mutex_opt in opts:
                if current_opt:
                    raise click.UsageError(
                        f"Illegal usage: "
                        f"'{apply_cli_option_format(self.name)}' "
                        f"cannot be used together with "
                        f"'{apply_cli_option_format(mutex_opt)}'.",
                        ctx=ctx,
                    )
                else:
                    self.prompt = None
        return super().handle_parse_result(ctx, opts, args)


class LogsMaxLines(click.ParamType):
    """
    Custom click type for ``--max-lines`` option in the ``logs`` command.

    It accepts 'all' keyword or integer higher than 0.
    """

    name = "max_lines"

    def convert(self, value, param, ctx):
        if isinstance(value, int):
            return value
        if value == "all":
            return value
        try:
            number = int(value)
            if number < 1:
                raise ValueError("Not a positive number.")
            return number
        except ValueError:
            self.fail(
                f"{value!r} is not a positive integer or 'all' keyword",
                param,
                ctx,
            )


@click.group(name="composer-dev")
@click.version_option(version=version.__version__, prog_name="composer-dev")
def cli():
    """
    Composer Local Development is a tool to create, manage and run local
    development environment.
    """
    pass


verbose_mode = click.option(
    "--verbose", is_flag=True, default=False, help="More verbose output."
)
debug_mode = click.option(
    "--debug", is_flag=True, default=False, help="Print debug log lines."
)

option_port = click.option(
    "--web-server-port",
    "--port",
    type=click.IntRange(min=0, max=65536),
    help="Port used by Airflow web server ",
    show_default="read from the configuration file",
    metavar="PORT",
)


required_environment = click.argument(
    "environment",
    required=True,
    metavar="LOCAL_ENVIRONMENT_NAME",
)
optional_environment = click.argument(
    "environment",
    required=False,
    metavar="LOCAL_ENVIRONMENT_NAME",
)
option_location = click.option(
    "-l",
    "--location",
    default="us-central1",
    show_default=True,
    help="ID of the location or fully qualified identifier for the location. ",
    metavar="LOCATION",
)


@cli.command()
@click.option(
    "--from-source-environment",
    cls=MutuallyExclusiveOption,
    mutual=["from_image_version"],
    help="Name of your Composer environment to be used as a source",
    metavar="REMOTE_ENV_NAME",
)
@click.option(
    "--from-image-version",
    cls=MutuallyExclusiveOption,
    mutual=["from_source_environment"],
    help=f"Composer image version (See {constants.COMPOSER_VERSIONING_DOCS_LINK})",
    metavar="COMPOSER_VERSION",
)
@click.option(
    "-p",
    "--project",
    help="The Google Cloud project ID to use. ",
    show_default="project ID set in Cloud CLI",
    metavar="PROJECT_ID",
)
@option_location
@option_port
@click.option(
    "--dags-path",
    help="Path to DAGs folder. If it does not exist, it will be created.",
    show_default="'dags' directory in the environment directory",
    metavar="PATH",
    type=click.Path(file_okay=False),
)
@required_environment
@verbose_mode
@debug_mode
@errors.catch_exceptions()
def create(
    from_source_environment: str,
    from_image_version: str,
    project: Optional[str],
    location: str,
    web_server_port: Optional[int],
    environment: str,
    verbose: bool,
    debug: bool,
    dags_path: Optional[pathlib.Path] = None,
):
    """
    Create local Composer development environment.

    There are two methods of creating the local environment:

    - using --from-source-environment option
      (based on a given running instance of Composer environment)\n
      Example:
      ```
      composer-dev create --from-source-environment remote_composer_env --location us-central1 --project project_id --port 8081 --dags-path my_project/dags local_env_name
      ```
    - using --from-image-version option
      (based on a given Composer image version)\n
      Example:
      ```
      composer-dev create --from-image-version composer-2.0.17-airflow-2.2.5 --project project_id --port 8081 --dags-path my_project/dags local_env_name
      ```

    Composer CLI will create **composer** directory in
    current working directory and subdirectory with the name of the environment.

    It's possible to modify already created environment by modifying
    configuration files placed in the environment directory.

    The environment name of the local composer environment should be between
    3 and 40 characters long and only consist of alphanumeric characters,
    underscores and hyphens.
    """
    utils.setup_logging(verbose, debug)
    utils.assert_environment_name_is_valid(environment)
    if not from_source_environment and not from_image_version:
        raise click.UsageError(
            "Missing source of the environment. "
            "Provide either --from-source-environment or --from-image-version option."
        )
    project = utils.resolve_project_id(project)
    env_dir = pathlib.Path("composer", environment)
    if env_dir.is_dir():
        click.confirm(
            f"Environment '{env_dir}' already exist. Do you want to overwrite it?",
            abort=True,
        )
        LOG.info("Overriding already existing local environment.")

    if from_source_environment:
        env = composer_environment.Environment.from_source_environment(
            source_environment=from_source_environment,
            project=project,
            location=location,
            env_dir_path=env_dir,
            web_server_port=web_server_port,
            dags_path=dags_path,
        )
    else:
        env = composer_environment.Environment(
            image_version=from_image_version,
            project_id=project,
            location=location,
            env_dir_path=env_dir,
            port=web_server_port,
            dags_path=dags_path,
        )
    env.create()


@cli.command()
@optional_environment
@option_port
@verbose_mode
@debug_mode
@errors.catch_exceptions()
def start(
    environment: Optional[str],
    web_server_port: Optional[int],
    verbose: bool,
    debug: bool,
):
    """Start Composer environment."""
    utils.setup_logging(verbose, debug)
    env_path = files.resolve_environment_path(environment)
    env = composer_environment.Environment.load_from_config(
        env_path, web_server_port
    )
    console.get_console().print(f"Starting {env.name} composer environment...")
    env.start()


@cli.command()
@optional_environment
@verbose_mode
@debug_mode
@errors.catch_exceptions()
def stop(environment: Optional[str], verbose: bool, debug: bool):
    """
    Stop Composer environment.

    The local environment docker container will be stopped but not removed.
    """
    utils.setup_logging(verbose, debug)
    env_path = files.resolve_environment_path(environment)
    env = composer_environment.Environment.load_from_config(env_path, None)
    env.stop()
    console.get_console().print("Stopped composer local environment.")


@cli.command()
@optional_environment
@option_port
@verbose_mode
@debug_mode
@errors.catch_exceptions()
def restart(
    environment: Optional[str],
    web_server_port: Optional[int],
    verbose: bool,
    debug: bool,
):
    """
    Restart Composer environment.

    The local environment docker container will be stopped and removed before
    starting the environment again.
    """
    utils.setup_logging(verbose, debug)
    env_path = files.resolve_environment_path(environment)
    env = composer_environment.Environment.load_from_config(
        env_path, web_server_port
    )
    env.restart()


@cli.command()
@optional_environment
@verbose_mode
@debug_mode
@click.option(
    "-f", "--follow", is_flag=True, default=False, help="Follow log output."
)
@click.option(
    "-l",
    "--max-lines",
    default="all",
    type=LogsMaxLines(),
    help="Maximum number of lines to be printed.",
    metavar="MAX_LINES",
)
@errors.catch_exceptions()
def logs(
    environment: Optional[str],
    max_lines: Union[str, int],
    follow: bool,
    verbose: bool,
    debug: bool,
):
    """
    Print logs from the running Composer environment container.

    Defaults to printing all available log lines.

    To print last 10 lines from environment container logs:
    ```
    composer-dev logs --max-lines 10
    ```
    To print all previous lines from logs and follow output:
    ```
    composer-dev logs --follow
    ```
    """
    utils.setup_logging(verbose, debug)
    env_path = files.resolve_environment_path(environment)
    env = composer_environment.Environment.load_from_config(env_path, None)
    env.logs(follow, max_lines)


@verbose_mode
@debug_mode
@cli.command(name="list")
@errors.catch_exceptions()
def list_command(verbose: bool, debug: bool):
    """
    Print list of the Composer environments found in the current directory.
    """
    utils.setup_logging(verbose, debug)
    current_path = pathlib.Path.cwd().resolve()
    envs = files.get_environment_directories()
    environments_status = composer_environment.get_environments_status(envs)
    if environments_status:
        console.get_console().print(
            constants.ENVIRONMENTS_FOUND.format(path=current_path)
        )
        table = utils.get_environment_status_table(environments_status)
        console.get_console().print(table)
        console.get_console().print(constants.LIST_COMMAND_EPILOG)
    else:
        console.get_console().print(
            constants.ENVIRONMENTS_NOT_FOUND.format(path=current_path)
        )


@cli.command()
@optional_environment
@verbose_mode
@debug_mode
@errors.catch_exceptions()
def describe(environment: Optional[str], verbose: bool, debug: bool):
    """
    Describe Composer environment.

    Print environment details. Example usage:

    > composer-dev describe env_name

    Environment name is optional if there is only one environment in the
    composer directory.
    """
    utils.setup_logging(verbose, debug)
    env_path = files.resolve_environment_path(environment)
    env = composer_environment.Environment.load_from_config(env_path, None)
    env.describe()


@cli.command()
@optional_environment
@verbose_mode
@debug_mode
@click.option(
    "--skip-confirmation",
    is_flag=True,
    default=False,
    help="Do not require confirmation before removing the environment.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Force the environment removal even if it is running.",
)
@errors.catch_exceptions()
def remove(
    environment: Optional[str],
    verbose: bool,
    debug: bool,
    skip_confirmation: bool,
    force: bool,
):
    """
    Remove Composer environment.

    Remove environment directory and the docker container.

    > composer-dev remove env_name

    Environment name is optional if there is only one environment in the
    composer directory.
    """
    utils.setup_logging(verbose, debug)
    env_path = files.resolve_environment_path(environment)
    if not skip_confirmation:
        click.confirm(
            constants.REMOVE_ENV_CONFIRMATION_PROMPT.format(env_path=env_path),
            abort=True,
        )
    try:
        env = composer_environment.Environment.load_from_config(env_path, None)
    except errors.InvalidConfigurationError:
        md = rich.markdown.Markdown(
            constants.MALFORMED_CONFIG_REMOVING_CONTAINER
        )
        console.get_console().print(md)
    else:
        container = env.get_container(ignore_not_found=True)
        if container is not None:
            if container.status == constants.ContainerStatus.RUNNING:
                if not force:
                    raise click.UsageError(constants.USE_FORCE_TO_REMOVE_ERROR)
                container.stop()
            container.remove()
    shutil.rmtree(env_path)


# ignore_unknown_options is required to be able to pass options to airflow cmd
@cli.command(
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@required_environment
@verbose_mode
@debug_mode
@click.argument(
    "command",
    nargs=-1,
    required=True,
    metavar="COMMAND",
    type=click.UNPROCESSED,
)
@errors.catch_exceptions()
def run_airflow_cmd(
    environment: Optional[str], command: List[str], verbose: bool, debug: bool
):
    """
    Run command in Airflow.

    Command is executed in the selected, running environment. Examples:

    > composer-dev run-airflow-cmd env_name **info**

    > composer-dev run-airflow-cmd env_name **dags list**

    """
    utils.setup_logging(verbose, debug)
    env_path = files.resolve_environment_path(environment)
    env = composer_environment.Environment.load_from_config(env_path, None)
    env.run_airflow_command([*command])


@cli.command()
@click.option(
    "-p",
    "--project",
    help="The Google Cloud project ID to use. ",
    show_default="project ID set in Cloud CLI",
    metavar="PROJECT_ID",
)
@option_location
@click.option(
    "--include-past-releases",
    is_flag=True,
    default=False,
    help="Include past releases in listed versions.",
)
@click.option(
    "--limit",
    default=10,
    help="Number of versions to display.",
    metavar="LIMIT",
)
@verbose_mode
@debug_mode
@errors.catch_exceptions()
def list_available_versions(
    project: Optional[str],
    location: str,
    include_past_releases: bool,
    limit: int,
    verbose: bool,
    debug: bool,
):
    """List Airflow versions available in Composer."""
    utils.setup_logging(verbose, debug)
    project = utils.resolve_project_id(project)
    image_versions = utils.get_image_versions(
        project, location, include_past_releases
    )
    filtered = utils.filter_image_versions(image_versions)
    versions = utils.sort_and_limit_image_versions(filtered, limit)
    table = utils.get_image_versions_table(versions)
    console.get_console().print(table)
