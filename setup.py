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

import io
import os

import setuptools

name = "composer-dev"
module_name = "composer_local_dev"
description = "Local Development for Composer"
release_status = (
    "Development Status :: 4 - Beta"  # see https://pypi.org/classifiers/
)
dependencies = [
    "click>=7.0,<8.2",
    "docker>=7.0.0",
    "google-auth>=2.27.0",
    "google-cloud-orchestration-airflow>=1.2.0",
    "google-cloud-artifact-registry>=1.2.0",
    "rich_click==1.4.0",
]
extras = {
    "tests": ["pytest", "nox", "coverage"],
    "docs": [
        "sphinx",
        "sphinx-tabs==3.3.1",
        "sphinx-copybutton==0.3.3",
    ],
    "dev": [
        "pre-commit",
    ],
}

package_root = os.path.abspath(os.path.dirname(__file__))
packages = setuptools.find_packages(exclude=("tests",))

with io.open("README.md", "r") as fh:
    long_description = fh.read()

version = {}
with open(os.path.join(package_root, module_name, "version.py")) as fp:
    exec(fp.read(), version)
version = version["__version__"]

setuptools.setup(
    name=name,
    version=version,
    description=description,
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Google LLC",
    author_email="no-reply@google.com",
    license="Apache 2.0",
    url="https://github.com/GoogleCloudPlatform/composer-local-dev",
    keywords="google airflow composer local development",
    classifiers=[
        release_status,
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
        "Topic :: Internet",
    ],
    platforms="Posix; MacOS X; Windows",
    packages=packages,
    python_requires=">=3.9,<3.12",
    install_requires=dependencies,
    extras_require=extras,
    package_data={
        "": ["docker_files/entrypoint.sh", "docker_files/run_as_user.sh"]
    },
    zip_safe=False,
    entry_points={
        "console_scripts": "{name}={module_name}.__main__:cli".format(
            name=name, module_name=module_name
        ),
    },
)
