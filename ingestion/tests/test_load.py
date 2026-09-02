"""Tests for the loader's idempotency.

The loader's whole job is that re-running an extract is safe. Getting the
partition predicate wrong is the kind of bug that either duplicates a season
every night or silently deletes history, and neither shows up until the
numbers are already wrong.
"""

from datetime import date

import duckdb
import pytest

from ingestion import load

SNAPSHOT = date(2026, 3, 1)


@pytest.fixture
def warehouse(tmp_path, monkeypatch):
    path = tmp_path / "test.duckdb"
    monkeypatch.setenv("DUCKDB_PATH", str(path))
    monkeypatch.setenv("RAW_DATA_DIR", str(tmp_path / "raw"))
    return path


def _rows(warehouse, table):
    with duckdb.connect(str(warehouse), read_only=True) as con:
        return con.execute(f"select * from raw.{table} order by 1").fetchall()


def _game(game_id: str, season: int, home_score: int):
    return {
        "game_id": game_id,
        "season": season,
        "home_score": home_score,
        "away_score": 60,
    }


def test_first_load_creates_the_table(warehouse):
    count = load.load_to_duckdb("ncaa_games", [_game("1", 2026, 70)])

    assert count == 1
    assert len(_rows(warehouse, "ncaa_games")) == 1


def test_reloading_the_same_season_replaces_rather_than_appends(warehouse):
    load.load_to_duckdb("ncaa_games", [_game("1", 2026, 70), _game("2", 2026, 80)])
    load.load_to_duckdb("ncaa_games", [_game("1", 2026, 71), _game("2", 2026, 81)])

    rows = _rows(warehouse, "ncaa_games")
    assert len(rows) == 2, "a re-run must not duplicate the season"
    assert {row[2] for row in rows} == {71, 81}, "the newer scores should win"


def test_loading_one_season_leaves_other_seasons_alone(warehouse):
    load.load_to_duckdb("ncaa_games", [_game("1", 2025, 70)])
    load.load_to_duckdb("ncaa_games", [_game("2", 2026, 80)])

    seasons = {row[1] for row in _rows(warehouse, "ncaa_games")}
    assert seasons == {2025, 2026}, "loading 2026 must not delete 2025"


def test_ratings_partition_on_season_and_snapshot_together(warehouse):
    def rating(season, snapshot, value):
        return {"season": season, "snapshot_date": snapshot, "team_name": "A", "adj_oe": value}

    load.load_to_duckdb("ncaa_ratings", [rating(2026, date(2026, 3, 1), 110.0)])
    load.load_to_duckdb("ncaa_ratings", [rating(2026, date(2026, 3, 2), 111.0)])
    load.load_to_duckdb("ncaa_ratings", [rating(2026, date(2026, 3, 2), 112.0)])

    rows = _rows(warehouse, "ncaa_ratings")
    # Two snapshot dates survive; the repeated one was replaced, not appended.
    assert len(rows) == 2
    assert {row[3] for row in rows} == {110.0, 112.0}


def test_replace_all_truncates(warehouse):
    load.load_to_duckdb("ncaa_games", [_game("1", 2025, 70)])
    load.load_to_duckdb("ncaa_games", [_game("2", 2026, 80)], replace_all=True)

    rows = _rows(warehouse, "ncaa_games")
    assert len(rows) == 1
    assert rows[0][1] == 2026


def test_an_empty_extract_is_a_no_op(warehouse):
    assert load.load_to_duckdb("ncaa_games", []) == 0


def test_persist_writes_parquet_and_returns_counts(warehouse, tmp_path):
    counts = load.persist({"ncaa_games": [_game("1", 2026, 70)]}, SNAPSHOT)

    assert counts == {"ncaa_games": 1}
    assert (tmp_path / "raw" / "ncaa_games" / f"{SNAPSHOT.isoformat()}.parquet").exists()


def test_a_partial_load_replaces_only_what_it_carries(tmp_path, monkeypatch):
    """The property that makes a daily rolling window safe.

    Games were once keyed on the season, so a load deleted the whole season
    before inserting. Extracting a single day would have deleted five months of
    basketball and inserted one evening of it.
    """
    warehouse = tmp_path / "warehouse.duckdb"
    monkeypatch.setenv("DUCKDB_PATH", str(warehouse))

    season = [
        {"game_id": str(i), "season": 2026, "home_score": 70, "away_score": 68}
        for i in range(500)
    ]
    load.load_to_duckdb("ncaa_games", season)

    # One corrected game, as a daily window would deliver.
    load.load_to_duckdb(
        "ncaa_games",
        [{"game_id": "7", "season": 2026, "home_score": 99, "away_score": 68}],
    )

    with duckdb.connect(str(warehouse)) as con:
        total = con.execute("select count(*) from raw.ncaa_games").fetchone()[0]
        corrected = con.execute(
            "select home_score from raw.ncaa_games where game_id = '7'"
        ).fetchone()[0]

    assert total == 500, "a one-game load must not delete the season"
    assert corrected == 99, "the game it did carry should be corrected"


def test_a_snapshot_table_keeps_earlier_snapshots(tmp_path, monkeypatch):
    warehouse = tmp_path / "warehouse.duckdb"
    monkeypatch.setenv("DUCKDB_PATH", str(warehouse))

    monday = {"snapshot_date": date(2026, 1, 5), "team_id": "150", "location": "Duke"}
    tuesday = {"snapshot_date": date(2026, 1, 6), "team_id": "150", "location": "Duke"}

    load.load_to_duckdb("ncaa_teams", [monday])
    load.load_to_duckdb("ncaa_teams", [tuesday])

    with duckdb.connect(str(warehouse)) as con:
        total = con.execute("select count(*) from raw.ncaa_teams").fetchone()[0]

    # The same team on a new date is a new row, not a correction of the old one.
    assert total == 2
