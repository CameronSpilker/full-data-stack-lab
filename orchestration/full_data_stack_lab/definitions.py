"""The Dagster code location: assets, jobs, schedules, sensors, resources."""

from __future__ import annotations

from dagster import Definitions
from dagster_dbt import DbtCliResource

from .assets import dbt_models, github_raw_data, pypi_raw_data
from .jobs import (
    dbt_on_ingestion_sensor,
    dbt_transformation_job,
    full_pipeline_job,
    github_daily_schedule,
    github_ingestion_job,
    pypi_ingestion_job,
    weekly_pipeline_schedule,
)
from .project import dbt_project

defs = Definitions(
    assets=[github_raw_data, pypi_raw_data, dbt_models],
    jobs=[
        github_ingestion_job,
        pypi_ingestion_job,
        dbt_transformation_job,
        full_pipeline_job,
    ],
    schedules=[github_daily_schedule, weekly_pipeline_schedule],
    sensors=[dbt_on_ingestion_sensor],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
)
