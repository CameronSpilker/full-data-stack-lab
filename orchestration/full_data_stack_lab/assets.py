"""Assets: ingestion multi-assets feeding the dbt graph.

Each raw table gets its own asset key, matching the key dagster-dbt derives
for the corresponding dbt source (`raw/<table>`). That makes the lineage from
API call to tournament odds a single connected graph rather than two systems
that have to agree.

Note: this module deliberately does not use `from __future__ import
annotations`. Dagster reads the real `context` annotation to pick the
execution context type, and stringified annotations make that check fail.
"""

from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetSpec,
    MaterializeResult,
    multi_asset,
)
from dagster_dbt import DbtCliResource, dbt_assets
from ingestion.config import current_season, load_seasons, utc_today

from ingestion import cbd, load, torvik

from .project import dbt_project

TEAM_TABLES = ["ncaa_teams"]
GAME_TABLES = ["ncaa_games"]
BOX_TABLES = ["ncaa_team_box"]
LINE_TABLES = ["ncaa_betting_lines"]
RATING_TABLES = ["ncaa_ratings"]


def raw_key(table: str) -> AssetKey:
    """The asset key dagster-dbt derives for `source('raw', table)`."""
    return AssetKey(["raw", table])


def _specs(tables: list[str], description: str) -> list[AssetSpec]:
    return [
        AssetSpec(key=raw_key(table), group_name="ingestion", description=description)
        for table in tables
    ]


def _materialize(tables: list[str], counts: dict[str, int], **metadata):
    for table in tables:
        yield MaterializeResult(
            asset_key=raw_key(table),
            metadata={"rows": counts.get(table, 0), **metadata},
        )


@multi_asset(
    specs=_specs(TEAM_TABLES, "Division I team dimension from collegebasketballdata.com."),
    compute_kind="python",
    can_subset=False,
)
def team_dimension(context: AssetExecutionContext):
    """The team list and its conference membership.

    Conferences change in July and not again, so this is scheduled rarely.
    """
    snapshot = utc_today()
    season = current_season()
    counts = load.persist(cbd.extract_teams(season, snapshot), snapshot)
    yield from _materialize(TEAM_TABLES, counts, season=season.year)


@multi_asset(
    specs=_specs(GAME_TABLES, "Every game of every tracked season."),
    compute_kind="python",
    can_subset=False,
)
def game_results(context: AssetExecutionContext):
    """Scores and schedule for the current season.

    Only the current season is refreshed on a schedule: past seasons are
    finished, and re-pulling them every night would spend the API budget
    rewriting rows that cannot change.
    """
    snapshot = utc_today()
    season = current_season()
    counts = load.persist(cbd.extract_games([season]), snapshot)
    yield from _materialize(GAME_TABLES, counts, season=season.year)


@multi_asset(
    specs=_specs(BOX_TABLES, "Team box score lines for the current season."),
    compute_kind="python",
    can_subset=False,
)
def team_box_scores(context: AssetExecutionContext):
    """Per-game team box scores, which the four factors are computed from."""
    snapshot = utc_today()
    season = current_season()
    counts = load.persist(cbd.extract_box_scores([season]), snapshot)
    yield from _materialize(BOX_TABLES, counts, season=season.year)


@multi_asset(
    specs=_specs(LINE_TABLES, "Closing betting lines — the predictor's benchmark."),
    compute_kind="python",
    can_subset=False,
)
def betting_lines(context: AssetExecutionContext):
    """Sportsbook spreads and totals for the current season."""
    snapshot = utc_today()
    season = current_season()
    counts = load.persist(cbd.extract_lines([season]), snapshot)
    yield from _materialize(LINE_TABLES, counts, season=season.year)


@multi_asset(
    specs=_specs(RATING_TABLES, "Barttorvik adjusted efficiency ratings."),
    compute_kind="python",
    can_subset=False,
)
def efficiency_ratings(context: AssetExecutionContext):
    """T-Rank ratings for every tracked season.

    All seasons rather than just the current one: the ratings are cheap (one
    request each) and a rebuilt history is what lets the backtest run.
    """
    snapshot = utc_today()
    counts = load.persist(torvik.extract(load_seasons(), snapshot), snapshot)
    yield from _materialize(RATING_TABLES, counts, snapshot_date=snapshot.isoformat())


@dbt_assets(manifest=dbt_project.manifest_path)
def dbt_models(context: AssetExecutionContext, dbt: DbtCliResource):
    """Every dbt model, seed, and test as its own Dagster asset."""
    yield from dbt.cli(["build"], context=context).stream()
