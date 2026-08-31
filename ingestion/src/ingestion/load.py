"""Write extracted rows to Parquet, then load them into the DuckDB raw schema.

Parquet is the durable landing zone — every run is replayable from disk
without touching an API again. DuckDB is the serving copy that dbt reads.

Loads are idempotent, but what "the same data" means differs by table, so each
one declares the columns that partition it. A teams snapshot replaces one
snapshot date; a season of games replaces those seasons and leaves the rest of
history alone. Re-running any extract is always safe.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from .config import duckdb_path, raw_data_dir

log = logging.getLogger(__name__)

RAW_SCHEMA = "raw"

# The columns whose incoming values are cleared before a load. A run that
# re-extracts season 2026 deletes only season 2026.
PARTITION_COLUMNS: dict[str, tuple[str, ...]] = {
    "ncaa_teams": ("snapshot_date",),
    "ncaa_games": ("season",),
    "ncaa_team_box": ("season",),
    "ncaa_ratings": ("season", "snapshot_date"),
    "ncaa_betting_lines": ("season",),
}


def write_parquet(table_name: str, rows: list[dict[str, Any]], snapshot: date) -> Path | None:
    """Land one extract as a dated Parquet file. Returns None for empty extracts."""
    if not rows:
        log.warning("No rows extracted for %s; nothing written", table_name)
        return None

    target_dir = raw_data_dir() / table_name
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{snapshot.isoformat()}.parquet"

    pq.write_table(pa.Table.from_pylist(rows), path)
    log.info("Wrote %s rows to %s", len(rows), path)
    return path


def _delete_clause(
    rows: list[dict[str, Any]], columns: tuple[str, ...]
) -> tuple[str, list[Any]] | None:
    """Build a DELETE predicate covering exactly the partitions being loaded."""
    usable = [column for column in columns if column in rows[0]]
    if not usable:
        return None

    combinations = sorted({tuple(row.get(column) for column in usable) for row in rows})
    predicate = " or ".join(
        "(" + " and ".join(f"{column} = ?" for column in usable) + ")" for _ in combinations
    )
    params = [value for combination in combinations for value in combination]
    return predicate, params


def load_to_duckdb(
    table_name: str,
    rows: list[dict[str, Any]],
    replace_all: bool = False,
) -> int:
    """Load an extract into raw.<table_name>, replacing only what it covers."""
    if not rows:
        return 0

    arrow_table = pa.Table.from_pylist(rows)  # noqa: F841 — read by DuckDB below

    with duckdb.connect(str(duckdb_path())) as con:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {RAW_SCHEMA}")
        qualified = f"{RAW_SCHEMA}.{table_name}"

        exists = con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = ? AND table_name = ?",
            [RAW_SCHEMA, table_name],
        ).fetchone()[0]

        if not exists:
            con.execute(f"CREATE TABLE {qualified} AS SELECT * FROM arrow_table")
            log.info("Created %s with %s rows", qualified, len(rows))
            return len(rows)

        if replace_all:
            con.execute(f"DELETE FROM {qualified}")
        else:
            clause = _delete_clause(rows, PARTITION_COLUMNS.get(table_name, ("snapshot_date",)))
            if clause:
                predicate, params = clause
                con.execute(f"DELETE FROM {qualified} WHERE {predicate}", params)

        con.execute(f"INSERT INTO {qualified} SELECT * FROM arrow_table")

    log.info("Loaded %s rows into %s", len(rows), qualified)
    return len(rows)


def persist(
    tables: dict[str, list[dict[str, Any]]],
    snapshot: date,
    replace_all: bool = False,
) -> dict[str, int]:
    """Land every extracted table to Parquet and load it into DuckDB."""
    counts: dict[str, int] = {}
    for table_name, rows in tables.items():
        write_parquet(table_name, rows, snapshot)
        counts[table_name] = load_to_duckdb(table_name, rows, replace_all)
    return counts
