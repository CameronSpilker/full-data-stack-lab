"""Write extracted rows to Parquet, then load them into the DuckDB raw schema.

Parquet is the durable landing zone — every run is replayable from disk
without touching an API again. DuckDB is the serving copy that dbt reads.

Loads are idempotent upserts: each table declares the columns that identify a
row, and a load replaces exactly the rows it carries and nothing else.

That matters more than it sounds. Games used to be keyed on the season, so a
load deleted the whole season before inserting. Re-extracting a season was
therefore safe, and extracting a single day was catastrophic: it would delete
five months of basketball and insert one evening of it. Keying on the row makes
a partial extract safe, which is what lets the daily run fetch a rolling window
instead of the entire season every night.
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

# What identifies a row in each table. A load deletes the rows matching the
# keys it is about to insert, so re-running any extract, whole season or single
# day, replaces exactly what it covers.
KEY_COLUMNS: dict[str, tuple[str, ...]] = {
    # Team and rating rows are dated snapshots: the same team on a new date is
    # a new row, not a correction of the old one.
    "ncaa_teams": ("snapshot_date", "team_id"),
    "ncaa_ratings": ("season", "snapshot_date", "team_id"),
    # Game-level facts are history, corrected in place when a score changes.
    "ncaa_games": ("game_id",),
    "ncaa_team_box": ("game_id", "team_id"),
    "ncaa_betting_lines": ("game_id", "provider"),
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


INCOMING = "incoming_rows"


def _delete_matching(con: Any, qualified: str, table_name: str, columns: list[str]) -> None:
    """Delete the rows the incoming extract is about to replace.

    Matched by an anti-join against the incoming batch rather than a generated
    predicate: a season is six thousand games, and an OR of six thousand
    clauses is a query no planner should be asked to read.
    """
    keys = [column for column in KEY_COLUMNS.get(table_name, ()) if column in columns]
    if not keys:
        log.warning("No key columns for %s; inserting without replacing", table_name)
        return

    matched = " and ".join(f"incoming.{key} = existing.{key}" for key in keys)
    con.execute(
        f"DELETE FROM {qualified} existing WHERE EXISTS ("
        f"  SELECT 1 FROM {INCOMING} incoming WHERE {matched}"
        f")"
    )


def load_to_duckdb(
    table_name: str,
    rows: list[dict[str, Any]],
    replace_all: bool = False,
) -> int:
    """Load an extract into raw.<table_name>, replacing only what it covers."""
    if not rows:
        return 0

    arrow_table = pa.Table.from_pylist(rows)

    with duckdb.connect(str(duckdb_path())) as con:
        # Registered by name rather than left to DuckDB's scan of local
        # variables, so the helpers below can see it too.
        con.register(INCOMING, arrow_table)
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {RAW_SCHEMA}")
        qualified = f"{RAW_SCHEMA}.{table_name}"

        exists = con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = ? AND table_name = ?",
            [RAW_SCHEMA, table_name],
        ).fetchone()[0]

        if not exists:
            con.execute(f"CREATE TABLE {qualified} AS SELECT * FROM {INCOMING}")
            log.info("Created %s with %s rows", qualified, len(rows))
            return len(rows)

        if replace_all:
            con.execute(f"DELETE FROM {qualified}")
        else:
            _delete_matching(con, qualified, table_name, list(rows[0]))

        con.execute(f"INSERT INTO {qualified} SELECT * FROM {INCOMING}")

    log.info("Loaded %s rows into %s", len(rows), qualified)
    return len(rows)


def known_conferences() -> list[str]:
    """Conference names the warehouse already holds, for the current season.

    The box score endpoint is walked one league at a time, and the list of
    leagues comes from `/teams`. When that endpoint is throttled the walk
    cannot start, which costs a run its box scores over a lookup whose answer
    is sitting in the warehouse from the last time it succeeded.

    Only the season the dimension was last extracted for. A backfill reaching
    into 2022 wants leagues that have since folded, so this is a fallback for
    when the source will not answer rather than a replacement for asking it.
    Returns an empty list when there is no warehouse yet, which is the first
    run and correctly falls through to the API.
    """
    path = duckdb_path()
    if not path.exists():
        return []

    try:
        with duckdb.connect(str(path), read_only=True) as con:
            rows = con.execute(
                """
                select distinct conference_name
                from raw.ncaa_teams
                where conference_name is not null and conference_name <> ''
                order by 1
                """
            ).fetchall()
    except duckdb.Error as exc:
        log.warning("No conference list in the warehouse: %s", exc)
        return []

    return [row[0] for row in rows]


def season_activity(season_year: int) -> tuple[date | None, date | None]:
    """The newest game on record for a season, and the newest one played.

    Answers the only question a scheduled run needs before it calls anything:
    is there anything left to fetch for this season, or is it history that
    settled months ago?

    Two dates rather than one, because they answer different questions. The
    newest game on record includes fixtures nobody has played yet, so it says
    whether a schedule exists ahead of us. The newest completed game says
    whether results are still arriving. A season sitting between them is in
    progress; a season whose last fixture is long past is over.

    Returns (None, None) when there is no warehouse, no games table, or no
    games for that season. That is the first run, or a season nobody has
    extracted yet, and the caller must treat it as "fetch it" rather than as
    "nothing to do": knowing nothing is not the same as knowing it is over.
    """
    path = duckdb_path()
    if not path.exists():
        return (None, None)

    try:
        with duckdb.connect(str(path), read_only=True) as con:
            row = con.execute(
                """
                select
                    max(try_cast(game_date as date)),
                    max(try_cast(game_date as date)) filter (where is_completed)
                from raw.ncaa_games
                where season = ?
                """,
                [season_year],
            ).fetchone()
    except duckdb.Error as exc:
        log.warning("No game history in the warehouse for %s: %s", season_year, exc)
        return (None, None)

    if not row:
        return (None, None)
    return (row[0], row[1])


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
