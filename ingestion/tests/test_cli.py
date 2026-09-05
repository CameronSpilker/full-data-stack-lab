"""What each `ingest` mode actually asks the source for.

The dispatch is a handful of conditionals, which is exactly the kind of code
that quietly acquires an extra extractor. It is also the code that decides
what a scheduled run spends its API budget on, and the daily pipeline spent
three days failing on a request it did not need to make, so the modes are
pinned here rather than left to be read off the source.
"""

import pytest

from ingestion import cli

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
