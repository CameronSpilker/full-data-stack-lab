"""Write extracted rows to Parquet, then load them into the DuckDB raw schema.

Parquet is the durable landing zone — every run is replayable from disk
without touching an API again. DuckDB is the serving copy that dbt reads.

Loads are idempotent: re-running an extract for a snapshot date replaces that
date's rows rather than appending duplicates.
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


def load_to_duckdb(
    table_name: str,
    rows: list[dict[str, Any]],
    snapshot: date,
    replace_all: bool = False,
) -> int:
    """Load an extract into raw.<table_name>.

    By default only the given snapshot date is replaced, so a re-run of one
    day is idempotent and earlier history survives. `replace_all` truncates
    the table first, for extracts that carry their own full history.
    """
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

        if exists:
            if replace_all:
                con.execute(f"DELETE FROM {qualified}")
            else:
                con.execute(f"DELETE FROM {qualified} WHERE snapshot_date = ?", [snapshot])
            con.execute(f"INSERT INTO {qualified} SELECT * FROM arrow_table")
        else:
            con.execute(f"CREATE TABLE {qualified} AS SELECT * FROM arrow_table")

    log.info("Loaded %s rows into %s.%s", len(rows), RAW_SCHEMA, table_name)
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
        counts[table_name] = load_to_duckdb(table_name, rows, snapshot, replace_all)
    return counts
