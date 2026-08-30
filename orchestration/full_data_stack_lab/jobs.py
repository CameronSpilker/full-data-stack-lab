"""Jobs, schedules, and the sensor that chains ingestion into dbt."""

from __future__ import annotations

from dagster import (
    AssetSelection,
    DefaultSensorStatus,
    RunRequest,
    ScheduleDefinition,
    SkipReason,
    asset_sensor,
    define_asset_job,
)

from .assets import GITHUB_TABLES, PYPI_TABLES, dbt_models, raw_key

github_ingestion_job = define_asset_job(
    name="github_ingestion_job",
    selection=AssetSelection.assets(*[raw_key(t) for t in GITHUB_TABLES]),
    description="Snapshot repo, contributor, and release metrics from GitHub.",
)

pypi_ingestion_job = define_asset_job(
    name="pypi_ingestion_job",
    selection=AssetSelection.assets(*[raw_key(t) for t in PYPI_TABLES]),
    description="Pull the trailing window of PyPI download counts.",
)

dbt_transformation_job = define_asset_job(
    name="dbt_transformation_job",
    selection=AssetSelection.assets(dbt_models),
    description="Run staging, intermediate, and mart models, then the full test suite.",
)

full_pipeline_job = define_asset_job(
    name="full_pipeline_job",
    selection=AssetSelection.all(),
    description="Ingestion followed by the whole dbt graph.",
)

# GitHub metrics only move meaningfully week to week, and the API budget is
# small, so daily is the useful floor rather than hourly.
github_daily_schedule = ScheduleDefinition(
    name="github_daily_schedule",
    job=github_ingestion_job,
    cron_schedule="0 6 * * *",
    execution_timezone="America/Denver",
)

weekly_pipeline_schedule = ScheduleDefinition(
    name="weekly_pipeline_schedule",
    job=full_pipeline_job,
    cron_schedule="0 7 * * 1",
    execution_timezone="America/Denver",
)


@asset_sensor(
    asset_key=raw_key("github_repos"),
    job=dbt_transformation_job,
    default_status=DefaultSensorStatus.STOPPED,
    description="Rebuild the dbt graph as soon as fresh GitHub data lands.",
)
def dbt_on_ingestion_sensor(context, asset_event):
    materialization = asset_event.dagster_event.step_materialization_data.materialization
    if not materialization:
        return SkipReason("No materialization payload on the event.")

    return RunRequest(run_key=context.cursor)
