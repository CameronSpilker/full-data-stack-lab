"""Parser tests for the collegebasketballdata.com extractor.

The network is not available in CI, and the point of these tests is not to
check that CBD is up. It is to pin down how a payload becomes a warehouse row,
so that when the API shape changes the failure is a specific assertion here
rather than a column of nulls in a mart three layers away.

The fixtures follow CBD's documented schema. Where a field is known to be
spelled more than one way across endpoints, both spellings are exercised.
"""

from datetime import date

import pytest

from ingestion import cbd

SNAPSHOT = date(2026, 3, 1)

GAME = {
    "id": 401638562,
    "season": 2026,
    "seasonType": "regular",
    "startDate": "2026-02-14T23:00:00.000Z",
    "neutralSite": False,
    "conferenceGame": True,
    "status": "final",
    "attendance": 9314,
    "venue": "Cameron Indoor Stadium",
    "homeTeamId": 150,
    "homeTeam": "Duke",
    "homeConferenceId": 2,
    "homePoints": 78,
    "awayTeamId": 152,
    "awayTeam": "North Carolina",
    "awayConferenceId": 2,
    "awayPoints": 74,
}


def test_parse_game_maps_the_documented_shape():
    row = cbd.parse_game(GAME, 2026)

    assert row["game_id"] == "401638562"
    assert row["season"] == 2026
    assert row["game_date"] == "2026-02-14"
    assert row["home_team_id"] == "150"
    assert row["away_team_id"] == "152"
    assert row["home_score"] == 78
    assert row["away_score"] == 74
    assert row["is_completed"] is True
    assert row["is_conference_game"] is True
    assert row["is_neutral_site"] is False
    assert row["season_type"] == 2


def test_parse_game_accepts_the_alternate_spellings():
    alternate = {
        "gameId": 999,
        "gameDate": "2026-03-20T18:00:00Z",
        "homeId": 1,
        "awayId": 2,
        "homeScore": 61,
        "awayScore": 70,
        "gameStatus": "completed",
        "seasonType": "postseason",
    }

    row = cbd.parse_game(alternate, 2026)

    assert row["game_id"] == "999"
    assert row["home_score"] == 61
    assert row["away_score"] == 70
    assert row["season_type"] == 3, "a postseason game must not be typed as regular season"


def test_parse_game_treats_an_unplayed_game_as_incomplete():
    scheduled = dict(GAME)
    scheduled.update({"status": "scheduled", "homePoints": None, "awayPoints": None})

    row = cbd.parse_game(scheduled, 2026)

    assert row["is_completed"] is False
    assert row["home_score"] is None


def test_parse_game_rejects_a_payload_missing_a_team():
    assert cbd.parse_game({"id": 1, "homeTeamId": 5}, 2026) is None
    assert cbd.parse_game({"homeTeamId": 5, "awayTeamId": 6}, 2026) is None


def test_parse_team_reads_conference_and_venue():
    team = {
        "id": 150,
        "school": "Duke",
        "mascot": "Blue Devils",
        "abbreviation": "DUKE",
        "conference": "ACC",
        "conferenceId": 2,
        "venue": {"name": "Cameron Indoor Stadium", "city": "Durham", "state": "NC"},
    }

    row = cbd.parse_team(team, SNAPSHOT)

    assert row["team_id"] == "150"
    assert row["location"] == "Duke"
    assert row["conference_name"] == "ACC"
    assert row["venue_city"] == "Durham"
    assert row["snapshot_date"] == SNAPSHOT


def test_parse_team_handles_a_venue_given_as_a_string():
    row = cbd.parse_team({"id": 1, "school": "Test", "venue": "Some Arena"}, SNAPSHOT)

    assert row["venue_name"] == "Some Arena"


def test_parse_team_box_reads_stats_flat_or_nested():
    flat = {
        "gameId": 1,
        "teams": [
            {
                "teamId": 150,
                "team": "Duke",
                "fieldGoalsMade": 28,
                "fieldGoalsAttempted": 58,
                "threePointFieldGoalsMade": 9,
                "turnovers": 11,
            }
        ],
    }
    nested = {
        "gameId": 2,
        "teams": [
            {
                "teamId": 152,
                "team": "North Carolina",
                "stats": {
                    "fieldGoalsMade": 26,
                    "fieldGoalsAttempted": 61,
                    "turnovers": 14,
                },
            }
        ],
    }

    flat_row = cbd.parse_team_box(flat, 2026)[0]
    nested_row = cbd.parse_team_box(nested, 2026)[0]

    assert flat_row["field_goals_made"] == 28
    assert flat_row["three_pointers_made"] == 9
    assert nested_row["field_goals_attempted"] == 61
    assert nested_row["turnovers"] == 14


def test_parse_lines_returns_one_row_per_book():
    entry = {
        "gameId": 401638562,
        "lines": [
            {"provider": "DraftKings", "spread": -4.5, "overUnder": 148.5},
            {"provider": "Bovada", "spread": -5.0, "overUnder": 149.0},
        ],
    }

    rows = cbd.parse_lines(entry, 2026)

    assert len(rows) == 2
    assert {row["provider"] for row in rows} == {"DraftKings", "Bovada"}
    assert rows[0]["game_id"] == "401638562"
    assert rows[0]["spread"] == -4.5


def test_parse_lines_tolerates_a_game_with_no_line():
    assert cbd.parse_lines({"gameId": 1, "lines": []}, 2026) == []
    assert cbd.parse_lines({"gameId": 1}, 2026) == []


def test_a_live_extract_without_a_key_fails_loudly(monkeypatch):
    # Silently producing zero rows would let a scheduled run "succeed" while
    # the warehouse quietly went stale.
    monkeypatch.delenv("CBD_API_KEY", raising=False)

    with pytest.raises(cbd.MissingApiKey, match="CBD_API_KEY"):
        cbd.api_key()
