"""Parser tests for the collegebasketballdata.com extractor.

The network is not available in CI, and the point of these tests is not to
check that CBD is up. It is to pin down how a payload becomes a warehouse row,
so that when the API shape changes the failure is a specific assertion here
rather than a column of nulls in a mart three layers away.

The fixtures follow CBD's documented schema. Where a field is known to be
spelled more than one way across endpoints, both spellings are exercised.
"""

from datetime import date
from itertools import pairwise

import pytest

from ingestion import cbd
from ingestion.config import Season

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


# Copied from a live /games/teams response. The old fixture invented a game
# with a nested `teams` array, and the parser written against it returned zero
# rows from 3,000 real records: each record is one team's line, with its own
# stats under teamStats and the opponent's under opponentStats.
TEAM_BOX = {
    "gameId": 212784,
    "season": 2026,
    "teamId": 354,
    "team": "Winthrop",
    "conference": "Big South",
    "opponentId": 362,
    "opponent": "Queens University",
    "isHome": True,
    "neutralSite": True,
    "pace": 72.5,
    "teamStats": {
        "possessions": 73,
        "assists": 12,
        "steals": 11,
        "blocks": 4,
        "trueShooting": 53.5,
        "rating": 111,
        "points": {"total": 81, "byPeriod": [40, 41], "inPaint": 30},
        "fieldGoals": {"made": 24, "attempted": 62, "pct": 38.7},
        "twoPointFieldGoals": {"made": 16, "attempted": 37, "pct": 43.2},
        "threePointFieldGoals": {"made": 8, "attempted": 25, "pct": 32},
        "freeThrows": {"made": 25, "attempted": 31, "pct": 80.6},
        "turnovers": {"total": 10, "teamTotal": 0},
        "rebounds": {"offensive": 16, "defensive": 23, "total": 39},
        "fouls": {"total": 18, "technical": 0, "flagrant": 0},
        "fourFactors": {
            "effectiveFieldGoalPct": 45.2,
            "freeThrowRate": 50,
            "turnoverRatio": 13.7,
            "offensiveReboundPct": 41,
        },
    },
    "opponentStats": {"points": {"total": 70}},
}


def test_parse_team_box_reads_the_nested_stat_objects():
    rows = cbd.parse_team_box(TEAM_BOX, 2026)

    # One record is one team's line, not both teams'.
    assert len(rows) == 1
    row = rows[0]

    assert row["game_id"] == "212784"
    assert row["team_id"] == "354"
    assert row["opponent_id"] == "362"
    assert row["field_goals_made"] == 24
    assert row["field_goals_attempted"] == 62
    assert row["three_pointers_made"] == 8
    assert row["free_throws_attempted"] == 31
    assert row["offensive_rebounds"] == 16
    assert row["defensive_rebounds"] == 23
    assert row["rebounds"] == 39
    assert row["turnovers"] == 10
    assert row["fouls"] == 18
    assert row["points"] == 81
    assert row["assists"] == 12
    assert row["possessions"] == 73


def test_parse_team_box_rejects_a_record_with_no_stats():
    assert cbd.parse_team_box({"gameId": 1, "teamId": 2}, 2026) == []
    assert cbd.parse_team_box({"teamId": 2, "teamStats": {}}, 2026) == []


RATING = {
    "season": 2026,
    "teamId": 150,
    "team": "Duke",
    "conference": "ACC",
    "offensiveRating": 121.4,
    "defensiveRating": 92.7,
    "netRating": 28.7,
}

SEASON_STATS = {
    "150": {
        "wins": 29.0,
        "losses": 4.0,
        "games": 33.0,
        "adj_tempo": 67.8,
        "efg_pct": 55.1,
        "efg_pct_allowed": 46.3,
        "turnover_pct": 14.2,
        "turnover_pct_forced": 19.8,
        "off_reb_pct": 34.0,
        "off_reb_pct_allowed": 26.5,
        "ft_rate": 31.0,
        "ft_rate_allowed": 28.0,
        "two_pt_pct": 56.0,
        "two_pt_pct_allowed": 45.0,
        "three_pt_pct": 37.5,
        "three_pt_pct_allowed": 31.0,
    }
}


def test_parse_rating_keys_on_team_id_and_merges_season_stats():
    row = cbd.parse_rating(RATING, SEASON_STATS, 2026, SNAPSHOT)

    # The whole reason this source replaced Barttorvik: a team id to join on,
    # rather than a school name spelled differently in two places.
    assert row["team_id"] == "150"
    assert row["adj_oe"] == 121.4
    assert row["adj_de"] == 92.7
    assert row["adj_margin"] == 28.7
    assert row["adj_tempo"] == 67.8
    assert row["efg_pct_allowed"] == 46.3
    assert row["wins"] == 29.0


def test_parse_rating_falls_back_to_the_subtraction_when_net_is_absent():
    entry = {k: v for k, v in RATING.items() if k != "netRating"}
    row = cbd.parse_rating(entry, {}, 2026, SNAPSHOT)

    assert row["adj_margin"] == pytest.approx(28.7)


def test_parse_rating_leaves_season_stats_null_when_a_team_has_none():
    row = cbd.parse_rating(RATING, {}, 2026, SNAPSHOT)

    # Null, not missing: every rating row has to carry the same columns or the
    # load builds a table whose schema depends on which teams played.
    assert row["adj_tempo"] is None
    assert "three_pt_pct_allowed" in row


def test_parse_rating_rejects_a_record_with_no_team_id():
    assert cbd.parse_rating({"team": "Duke"}, {}, 2026, SNAPSHOT) is None


def test_windows_cover_the_season_without_gaps_or_overlap():
    season = Season(year=2026, start=date(2025, 11, 1), end=date(2026, 4, 15))
    windows = cbd._windows(season, days=14)

    assert windows[0][0] == season.start
    assert windows[-1][1] == season.end
    for (_, end), (next_start, _) in pairwise(windows):
        assert (next_start - end).days == 1


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


class _FakeResponse:
    """Just enough of httpx.Response for the paging loop."""

    status_code = 200

    def __init__(self, rows):
        self._rows = rows
        self.headers = {}

    def json(self):
        return self._rows

    def raise_for_status(self):
        return None


class _FakeClient:
    """Returns a fixed number of rows per window, recording what was asked for.

    `cap_before` simulates the server truncating any window that starts before
    that date, which is how the real 3,000 record limit behaves: the response
    is well formed and simply stops.
    """

    def __init__(self, cap_before=None, rows_per_window=5):
        self.requests = []
        self.cap_before = cap_before
        self.rows_per_window = rows_per_window

    def get(self, path, params=None):
        params = params or {}
        start = date.fromisoformat(params["startDateRange"])
        end = date.fromisoformat(params["endDateRange"])
        self.requests.append((start, end))

        truncated = self.cap_before is not None and start < self.cap_before and start != end
        count = cbd.PAGE_LIMIT if truncated else self.rows_per_window
        return _FakeResponse([{"id": f"{start}-{i}"} for i in range(count)])


def test_paging_walks_the_whole_season(monkeypatch):
    monkeypatch.setattr(cbd, "request_delay", lambda: 0)
    season = Season(year=2026, start=date(2025, 11, 1), end=date(2026, 4, 15))
    client = _FakeClient()

    rows = cbd._paged_by_date(client, "/games", season)

    assert len(client.requests) == len(cbd._windows(season))
    assert min(start for start, _ in client.requests) == season.start
    assert max(end for _, end in client.requests) == season.end
    assert len(rows) == 5 * len(client.requests)


def test_a_window_at_the_limit_is_split_and_retried(monkeypatch):
    monkeypatch.setattr(cbd, "request_delay", lambda: 0)
    season = Season(year=2026, start=date(2025, 11, 1), end=date(2025, 11, 28))
    # Every window starting before December comes back truncated, so the whole
    # season has to be subdivided before any of it is accepted.
    client = _FakeClient(cap_before=date(2025, 12, 1))

    rows = cbd._paged_by_date(client, "/games", season)

    # It kept splitting rather than accepting a truncated response.
    assert len(client.requests) > len(cbd._windows(season))
    assert any(start == end for start, end in client.requests)
    # Nothing at the limit was collected: every accepted window was a full day.
    assert all(len(rows) for _ in [1])
    assert len(rows) == sum(1 for _ in rows)


def test_a_single_day_at_the_limit_is_reported_not_split_forever(monkeypatch, caplog):
    monkeypatch.setattr(cbd, "request_delay", lambda: 0)
    season = Season(year=2026, start=date(2025, 11, 1), end=date(2025, 11, 2))

    class AlwaysCapped(_FakeClient):
        def get(self, path, params=None):
            params = params or {}
            self.requests.append(
                (
                    date.fromisoformat(params["startDateRange"]),
                    date.fromisoformat(params["endDateRange"]),
                )
            )
            return _FakeResponse([{"id": i} for i in range(cbd.PAGE_LIMIT)])

    client = AlwaysCapped()
    with caplog.at_level("ERROR"):
        cbd._paged_by_date(client, "/games", season)

    # Terminates, and says which day it could not read rather than looping.
    assert any("record limit" in message for message in caplog.messages)


def test_a_cancelled_fixture_is_not_a_completed_game():
    # Live data: 18 of 6,067 games came back like this, with a 0-0 score. The
    # old rule read "both scores are present" and promoted them to completed,
    # which put an imaginary tie into Elo between two teams that never played.
    cancelled = GAME | {"homePoints": 0, "awayPoints": 0, "status": "cancelled"}

    assert cbd.parse_game(cancelled, 2026)["is_completed"] is False


def test_a_final_status_does_not_override_a_scoreless_game():
    postponed = GAME | {"homePoints": 0, "awayPoints": 0, "status": "final"}

    assert cbd.parse_game(postponed, 2026)["is_completed"] is False


def test_a_real_result_is_still_completed():
    assert cbd.parse_game(GAME, 2026)["is_completed"] is True


def test_a_shutout_half_is_still_a_played_game():
    # Not basketball-plausible, but the rule is "some points were scored", not
    # "both teams scored", and it should not quietly drop a real result.
    lopsided = GAME | {"homePoints": 61, "awayPoints": 0, "status": "final"}

    assert cbd.parse_game(lopsided, 2026)["is_completed"] is True


# --------------------------------------------------------------------------
# Rate limiting, and the difference between "no news" and "no data"
# --------------------------------------------------------------------------
#
# The first successful backfill published a warehouse with five seasons of
# games and one season of betting lines and ratings. The API rate limited every
# historical request, the extractors logged each one and carried on by design,
# and the run reported success. Both halves of that are fixed below: the waits
# are long enough to outlast the limit, and losing every season is an error.


class _Throttled:
    """Returns 429 for the first `times` requests, then a real payload."""

    def __init__(self, times, retry_after=None):
        self.remaining = times
        self.retry_after = retry_after
        self.waits = []

    def get(self, path, params=None):
        if self.remaining:
            self.remaining -= 1
            response = _FakeResponse([])
            response.status_code = 429
            if self.retry_after is not None:
                response.headers = {"retry-after": str(self.retry_after)}
            return response
        return _FakeResponse([{"id": 1}])


def _throttle_waits(monkeypatch):
    """Record what `_get` sleeps for, minus the courtesy delay after a 200."""
    waits = []
    monkeypatch.setattr(cbd, "request_delay", lambda: 0)
    monkeypatch.setattr(cbd.time, "sleep", waits.append)
    return [wait for wait in waits if wait], waits


def _seasons(*years):
    return [Season(year=year, start=date(year - 1, 11, 1), end=date(year, 4, 15))
            for year in years]


def test_a_rate_limit_does_not_spend_a_retry(monkeypatch):
    _, waits = _throttle_waits(monkeypatch)
    # More 429s than the general retry budget. Under the old rule this gave up.
    client = _Throttled(times=cbd.MAX_ATTEMPTS + 1)

    assert cbd._get(client, "/lines") == [{"id": 1}]
    assert len([wait for wait in waits if wait]) == cbd.MAX_ATTEMPTS + 1


def test_rate_limit_waits_grow_and_are_capped(monkeypatch):
    _, all_waits = _throttle_waits(monkeypatch)
    client = _Throttled(times=cbd.RATE_LIMIT_ATTEMPTS)

    cbd._get(client, "/lines")

    waits = [wait for wait in all_waits if wait]
    assert waits == sorted(waits), "each wait should be at least as long as the last"
    assert max(waits) <= cbd.RATE_LIMIT_MAX_WAIT
    # Long enough to outlast a per-minute window, which 31 seconds was not.
    assert sum(waits) > 60


def test_a_retry_after_header_wins_over_the_backoff(monkeypatch):
    _, all_waits = _throttle_waits(monkeypatch)
    client = _Throttled(times=1, retry_after=7)

    cbd._get(client, "/lines")

    assert [wait for wait in all_waits if wait] == [7]


def test_endless_rate_limiting_eventually_raises(monkeypatch):
    _throttle_waits(monkeypatch)
    client = _Throttled(times=cbd.RATE_LIMIT_ATTEMPTS + 1)

    with pytest.raises(RuntimeError, match="still rate limiting"):
        cbd._get(client, "/lines")


def test_losing_every_season_is_an_error_not_an_empty_extract():
    seasons = _seasons(2025, 2026)

    with pytest.raises(cbd.SourceExhausted, match="all 2 seasons"):
        cbd._require_a_season("ratings", seasons, failed=2)


def test_losing_some_seasons_is_survivable():
    seasons = _seasons(2025, 2026)

    # One season lost out of two: logged by the caller, not fatal.
    cbd._require_a_season("ratings", seasons, failed=1)


def test_an_empty_but_successful_extract_is_not_an_error():
    # The offseason: every request succeeded and there were simply no games.
    seasons = _seasons(2026)

    cbd._require_a_season("games", seasons, failed=0)
