"""The Dagster code location: assets, jobs, schedules, sensors, resources."""

from __future__ import annotations

from dagster import Definitions
from dagster_dbt import DbtCliResource

from .assets import (
    betting_lines,
    dbt_models,
    efficiency_ratings,
    game_results,
    team_box_scores,
    team_dimension,
)
from .jobs import (
    dbt_on_ingestion_sensor,
    dbt_transformation_job,
    full_pipeline_job,
    march_schedule,
    nightly_ingestion_job,
    nightly_schedule,
    team_dimension_job,
    team_dimension_schedule,
)
from .project import dbt_project

defs = Definitions(
    assets=[
        team_dimension,
        game_results,
        team_box_scores,
        betting_lines,
        efficiency_ratings,
        dbt_models,
    ],
    jobs=[
        nightly_ingestion_job,
        team_dimension_job,
        dbt_transformation_job,
        full_pipeline_job,
    ],
    schedules=[nightly_schedule, team_dimension_schedule, march_schedule],
    sensors=[dbt_on_ingestion_sensor],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
)
