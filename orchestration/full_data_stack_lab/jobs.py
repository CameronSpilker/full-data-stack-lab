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

from .assets import (
    BOX_TABLES,
    GAME_TABLES,
    LINE_TABLES,
    RATING_TABLES,
    TEAM_TABLES,
    dbt_models,
    raw_key,
)

nightly_ingestion_job = define_asset_job(
    name="nightly_ingestion_job",
    selection=AssetSelection.assets(
        *[raw_key(table) for table in GAME_TABLES + BOX_TABLES + LINE_TABLES + RATING_TABLES]
    ),
    description="Scores, box scores, lines, and ratings for the season in progress.",
)

team_dimension_job = define_asset_job(
    name="team_dimension_job",
    selection=AssetSelection.assets(*[raw_key(table) for table in TEAM_TABLES]),
    description="Refresh the team list and conference membership.",
)

dbt_transformation_job = define_asset_job(
    name="dbt_transformation_job",
    selection=AssetSelection.assets(dbt_models),
    description="Run staging, intermediate, and mart models, then the full test suite.",
)

full_pipeline_job = define_asset_job(
    name="full_pipeline_job",
    selection=AssetSelection.all(),
    description="Every extractor followed by the whole dbt graph.",
)

# Games finish late. 6am Mountain is after the last west coast final and
# before anyone looks at the dashboard.
nightly_schedule = ScheduleDefinition(
    name="nightly_in_season_schedule",
    job=nightly_ingestion_job,
    cron_schedule="0 6 * * *",
    execution_timezone="America/Denver",
    description=(
        "Daily during the season. Harmless out of season — the extractors "
        "return the same finished rows and the loader replaces them in place."
    ),
)

# Conference membership changes once a year, in July.
team_dimension_schedule = ScheduleDefinition(
    name="team_dimension_schedule",
    job=team_dimension_job,
    cron_schedule="0 5 1 * *",
    execution_timezone="America/Denver",
    description="Monthly. Conference realignment is an offseason event.",
)

# Selection Sunday through the final: the bracket moves every day, so the whole
# graph runs twice daily in March.
march_schedule = ScheduleDefinition(
    name="march_madness_schedule",
    job=full_pipeline_job,
    cron_schedule="0 7,19 * 3 *",
    execution_timezone="America/Denver",
    description="Twice daily through March, when the odds change between sessions.",
)


@asset_sensor(
    asset_key=raw_key("ncaa_games"),
    job=dbt_transformation_job,
    default_status=DefaultSensorStatus.STOPPED,
    description="Rebuild the dbt graph as soon as fresh scores land.",
)
def dbt_on_ingestion_sensor(context, asset_event):
    materialization = asset_event.dagster_event.step_materialization_data.materialization
    if not materialization:
        return SkipReason("No materialization payload on the event.")

    return RunRequest(run_key=context.cursor)
