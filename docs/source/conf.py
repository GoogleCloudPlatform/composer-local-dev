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

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
import datetime

from composer_local_dev.version import __version__

project = "Composer Local Development"
description = "Local Development for Google Composer"
copyright = f"{datetime.datetime.now().year}, Google"  # TODO: (b/226562556): Fill missing metadata
author = "Google"  # TODO: (b/226562556): Fill missing metadata

release = __version__
version = __version__
master_doc = "index"

extensions = ["sphinx_tabs.tabs", "sphinx_copybutton"]
exclude_patterns = []

html_theme = "alabaster"

html_theme_options = {
    "description": description,
    "logo_name": True,
    "logo_text_align": "center",
    "show_powered_by": False,
    "github_user": "",  # TODO: (b/226562556): Fill missing metadata
    "github_repo": "",  # TODO: (b/226562556): Fill missing metadata
    "github_banner": False,
    "github_button": True,
    "show_related": False,
    "note_bg": "#FFF59C",
    "github_type": "star",
}

html_static_path = ["_static"]
