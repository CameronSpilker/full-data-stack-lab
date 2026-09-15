"""What each `ingest` mode actually asks the source for.

The dispatch is a handful of conditionals, which is exactly the kind of code
that quietly acquires an extra extractor. It is also the code that decides
what a scheduled run spends its API budget on, and the daily pipeline spent
three days failing on a request it did not need to make, so the modes are
pinned here rather than left to be read off the source.
"""

from datetime import date

import pytest

from ingestion import cli
from ingestion.config import Season, _default_bounds

EXTRACTORS = ("teams", "games", "boxscores", "lines", "ratings")


def _asked_for(source: str) -> set[str]:
    return {name for name in EXTRACTORS if cli._wanted(source, name)}


def test_all_runs_every_extractor():
    assert _asked_for("all") == set(EXTRACTORS)


def test_daily_leaves_the_team_dimension_alone():
    # Conference membership changes once a year, in July. Re-reading it every
    # night spends the run's first requests on rows that cannot have moved,
    # and it is the first call the run makes, so a throttle there costs every
    # table behind it.
    assert "teams" not in _asked_for("daily")
    assert _asked_for("daily") == {"games", "boxscores", "lines", "ratings"}


@pytest.mark.parametrize("source", EXTRACTORS)
def test_naming_one_extractor_runs_only_that_one(source):
    assert _asked_for(source) == {source}


def test_daily_is_offered_on_the_command_line():
    assert "daily" in cli.SOURCES


# ---------------------------------------------------------------------------
# Which seasons a windowed run bothers to ask for
# ---------------------------------------------------------------------------
#
# The nightly run asked for the current season every night forever. That is
# right in March and waste in July, and the waste is not free: the box score
# walk is 31 requests per season per run, and five months of re-downloading a
# finished season is what rate limited the pipeline into failing outright.


def _season(year: int) -> Season:
    start, end = _default_bounds(year)
    return Season(year=year, start=start, end=end)


@pytest.fixture
def activity(monkeypatch):
    """Stand in for the warehouse, so these tests need no DuckDB file."""
    recorded: dict[int, tuple] = {}

    def fake(season_year: int):
        return recorded.get(season_year, (None, None))

    monkeypatch.setattr(cli.load, "season_activity", fake)
    return recorded


def test_a_season_whose_last_fixture_is_past_the_window_is_settled(activity):
    activity[2026] = (date(2026, 4, 7), date(2026, 4, 7))

    live, settled = cli._still_worth_fetching([_season(2026)], date(2026, 9, 8))

    assert live == []
    assert [season.year for season in settled] == [2026]


def test_a_season_with_a_fixture_inside_the_window_is_live(activity):
    activity[2026] = (date(2026, 3, 20), date(2026, 3, 18))

    live, settled = cli._still_worth_fetching([_season(2026)], date(2026, 3, 13))

    assert [season.year for season in live] == [2026]
    assert settled == []


def test_a_season_with_a_schedule_ahead_is_live_before_anyone_plays(activity):
    # The night a new schedule lands, every fixture is in the future and none
    # is complete. That is the case this gate must not mistake for an over
    # season, or the new season never starts extracting.
    activity[2027] = (date(2026, 11, 3), None)

    live, _ = cli._still_worth_fetching([_season(2027)], date(2026, 9, 8))

    assert [season.year for season in live] == [2027]


def test_a_season_the_warehouse_has_never_seen_is_live(activity):
    # Knowing nothing is not knowing it is over. This is the first run ever,
    # and a season added to seasons.yml that nobody has extracted yet.
    live, settled = cli._still_worth_fetching([_season(2027)], date(2026, 9, 8))

    assert [season.year for season in live] == [2027]
    assert settled == []


def test_a_backfill_is_never_gated(activity):
    # No window means "fetch all of it". A backfill is the one command that
    # exists to rebuild history, so it must not be talked out of it.
    activity[2022] = (date(2022, 4, 4), date(2022, 4, 4))

    live, settled = cli._still_worth_fetching([_season(2022)], None)

    assert [season.year for season in live] == [2022]
    assert settled == []


def test_box_scores_are_skipped_when_nothing_was_played(activity):
    # The box score endpoint takes no date filter, so the only way to narrow
    # it is to not call it. A window with no completed game behind it has no
    # box score at the other end of those 31 requests.
    activity[2027] = (date(2026, 11, 3), None)

    assert not cli._games_landed_recently([_season(2027)], date(2026, 9, 8))


def test_box_scores_run_when_a_game_was_played_in_the_window(activity):
    activity[2026] = (date(2026, 3, 20), date(2026, 3, 18))

    assert cli._games_landed_recently([_season(2026)], date(2026, 3, 13))


def test_box_scores_run_when_the_warehouse_knows_nothing(activity):
    assert cli._games_landed_recently([_season(2027)], date(2026, 9, 8))
