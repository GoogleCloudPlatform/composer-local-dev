# End To End Tests

End to end tests aim to cover all user journeys. Tests use pytest to prepare
environment and trigger the Composer Development CLI.

## Setup

To run the E2E tests locally you need to have configured
environment. It may differ depending on the tests but most tests require:

- a host system capable of running docker images,
- application default authorization using the gcloud cli,
- configured remote Composer service (enabled APIs)

You also need to set following environment variables:

- ``COMPOSER_TESTS_PROJECT_ID``: id of the remote Composer project

Following environment variable are optional:

- ``COMPOSER_TESTS_IMAGE_VERSION``: image version used for
  create --from-image-version command

## Running the test

Pytest can be used to run the tests. Since E2E tests require configured
environment and can take more time to execute, they are not run by default.
Add ``--e2e`` flag to the run command to run E2E tests:

```commandline
pytest --e2e tests/e2e/test_recreate_running.py
```
