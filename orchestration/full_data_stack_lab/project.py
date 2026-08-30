"""Locate the dbt project so Dagster can read its manifest.

`DBT_MANIFEST` lets a deployment point at a manifest built during CI instead
of building one at import time.
"""

from __future__ import annotations

import os
from pathlib import Path

from dagster_dbt import DbtProject

REPO_ROOT = Path(__file__).resolve().parents[2]
DBT_PROJECT_DIR = REPO_ROOT / "transform"

dbt_project = DbtProject(
    project_dir=DBT_PROJECT_DIR,
    profiles_dir=DBT_PROJECT_DIR,
    target=os.getenv("DBT_TARGET", "dev"),
)

# In development, build the manifest on import so `dagster dev` always
# reflects the models on disk. In production, prepare_if_dev() is a no-op and
# the manifest committed by CI is used as-is.
dbt_project.prepare_if_dev()
