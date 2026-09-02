"""Tests for the preflight coverage check.

The check's job is to notice a column that parsed to nothing. These tests are
about that judgement, not about the network — the extractors are exercised
against fixtures in test_cbd.py and test_torvik.py.
"""

from ingestion import preflight


def test_coverage_reports_a_full_column_as_complete():
    rows = [{"team_id": "1", "location": "A"}, {"team_id": "2", "location": "B"}]

    checks = {check.column: check for check in preflight.coverage(rows, "ncaa_teams")}

    assert checks["team_id"].coverage == 1.0
    assert checks["team_id"].rows == 2
    assert not checks["team_id"].failed


def test_a_column_that_parsed_to_nothing_fails():
    # The exact failure this exists to catch: the request succeeded, rows came
    # back, and the rating the predictor depends on is empty.
    rows = [{"team_name": "A", "adj_oe": None, "adj_de": None} for _ in range(10)]

    checks = {check.column: check for check in preflight.coverage(rows, "ncaa_ratings")}

    assert checks["adj_oe"].coverage == 0.0
    assert checks["adj_oe"].failed
    assert checks["team_name"].coverage == 1.0
    assert not checks["team_name"].failed


def test_partial_coverage_is_judged_against_the_threshold():
    # adj_oe needs 95%. Nine of ten is not enough.
    rows = [{"team_name": "T", "adj_oe": 110.0} for _ in range(9)]
    rows.append({"team_name": "T", "adj_oe": None})

    checks = {check.column: check for check in preflight.coverage(rows, "ncaa_ratings")}

    assert checks["adj_oe"].coverage == 0.9
    assert checks["adj_oe"].failed


def test_a_non_critical_column_never_fails():
    # Seeds are absent for most of the season, and that is not a problem.
    rows = [{"team_name": "T", "adj_oe": 110.0, "seed": None} for _ in range(10)]

    checks = {check.column: check for check in preflight.coverage(rows, "ncaa_ratings")}

    assert checks["seed"].coverage == 0.0
    assert not checks["seed"].is_critical
    assert not checks["seed"].failed


def test_unplayed_games_do_not_fail_the_games_check():
    # Half the season is unplayed in December. Scores are deliberately not
    # critical fields, because a null there is the shape of the data.
    rows = [
        {"game_id": str(i), "game_date": "2026-01-01", "home_team_id": "1",
         "away_team_id": "2", "home_score": None}
        for i in range(10)
    ]

    checks = preflight.coverage(rows, "ncaa_games")

    assert not any(check.failed for check in checks)


def test_no_rows_yields_no_checks():
    assert preflight.coverage([], "ncaa_games") == []


def test_every_critical_table_is_a_real_raw_table():
    from ingestion.load import KEY_COLUMNS

    # A threshold on a table the loader does not know about would never run.
    assert set(preflight.CRITICAL) <= set(KEY_COLUMNS)
