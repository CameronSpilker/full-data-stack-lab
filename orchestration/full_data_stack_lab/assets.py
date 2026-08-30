"""Assets: ingestion multi-assets feeding the dbt graph.

Each raw table gets its own asset key, matching the key dagster-dbt derives
for the corresponding dbt source (`raw/<table>`). That makes the lineage from
API call to mart a single connected graph rather than two systems that have
to agree.

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
from ingestion.config import load_tools, utc_today

from ingestion import github, load, pypi

from .project import dbt_project

GITHUB_TABLES = ["github_repos", "github_contributors", "github_releases"]
PYPI_TABLES = ["pypi_downloads"]


def raw_key(table: str) -> AssetKey:
    """The asset key dagster-dbt derives for `source('raw', table)`."""
    return AssetKey(["raw", table])


def _specs(tables: list[str], description: str) -> list[AssetSpec]:
    return [
        AssetSpec(key=raw_key(table), group_name="ingestion", description=description)
        for table in tables
    ]


@multi_asset(
    specs=_specs(GITHUB_TABLES, "Dated snapshot from the GitHub REST API."),
    compute_kind="python",
    can_subset=False,
)
def github_raw_data(context: AssetExecutionContext):
    """Snapshot repo, contributor, and release metrics for every tracked tool."""
    snapshot = utc_today()
    tables = github.extract(load_tools(), snapshot)
    counts = load.persist(tables, snapshot)

    for table in GITHUB_TABLES:
        yield MaterializeResult(
            asset_key=raw_key(table),
            metadata={"rows": counts.get(table, 0), "snapshot_date": snapshot.isoformat()},
        )


@multi_asset(
    specs=_specs(PYPI_TABLES, "Daily download counts from the pypistats API."),
    compute_kind="python",
    can_subset=False,
)
def pypi_raw_data(context: AssetExecutionContext):
    """Pull the trailing window of download counts for every tracked package."""
    snapshot = utc_today()
    tables = pypi.extract(load_tools(), snapshot)
    counts = load.persist(tables, snapshot)

    for table in PYPI_TABLES:
        yield MaterializeResult(
            asset_key=raw_key(table),
            metadata={"rows": counts.get(table, 0), "snapshot_date": snapshot.isoformat()},
        )


@dbt_assets(manifest=dbt_project.manifest_path)
def dbt_models(context: AssetExecutionContext, dbt: DbtCliResource):
    """Every dbt model, seed, and test as its own Dagster asset."""
    yield from dbt.cli(["build"], context=context).stream()
