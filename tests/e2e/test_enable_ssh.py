import pathlib

import pytest

from tests.e2e import (
    assert_example_dag_listed,
    assert_example_dag_succeeded,
    run_app,
)


@pytest.mark.e2e
def test_enable_ssh_airflow(composer_image_version, valid_project_id, env_name):
    dags_dir = pathlib.Path(__file__).parent / "example_dag"
    run_app(
        f"create --from-image-version {composer_image_version} "
        f"-p {valid_project_id} --dags-path {dags_dir} "
        f"--enable-ssh {env_name}"
    )
    run_app(f"start {env_name}")
    assert_example_dag_listed()
    assert_example_dag_succeeded(env_name, airflow_major_version=2)
    run_app(f"stop {env_name}")


@pytest.mark.e2e
def test_enable_ssh_airflow_3(
    composer_image_version_airflow_3, valid_project_id, env_name
):
    dags_dir = pathlib.Path(__file__).parent / "example_dag"
    run_app(
        f"create --from-image-version {composer_image_version_airflow_3} "
        f"-p {valid_project_id} --dags-path {dags_dir} "
        f"--enable-ssh {env_name}"
    )
    # Copy requirements.txt with already satisfied deps to our environment
    run_app(f"start {env_name}")
    assert_example_dag_listed()
    assert_example_dag_succeeded(env_name, airflow_major_version=3)
    run_app(f"stop {env_name}")
