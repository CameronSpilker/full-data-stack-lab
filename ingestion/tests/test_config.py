from datetime import date

import pytest

from ingestion.config import Season, current_season, load_seasons


def test_registry_loads_and_is_ordered():
    seasons = load_seasons()

    assert seasons, "the registry should not be empty"
    years = [season.year for season in seasons]
    assert years == sorted(years), "seasons must come back oldest first"
    assert len(set(years)) == len(years), "season years must be unique"


def test_season_bounds_cover_a_real_season():
    for season in load_seasons():
        # November through April. A season that does not span the new year has
        # been configured wrong, and every date walk would silently miss games.
        assert season.start.year == season.year - 1
        assert season.end.year == season.year
        assert season.start < season.end


def test_season_label_reads_the_way_people_write_it():
    season = Season(year=2026, start=date(2025, 11, 1), end=date(2026, 4, 15))

    assert season.label == "2025-26"


def test_season_dates_are_contiguous_and_inclusive():
    season = Season(year=2026, start=date(2025, 11, 1), end=date(2025, 11, 5))

    assert season.dates() == [date(2025, 11, day) for day in range(1, 6)]
    assert season.contains(date(2025, 11, 3))
    assert not season.contains(date(2025, 10, 31))


def test_current_season_is_in_the_registry():
    season = current_season()

    assert season.year in {registered.year for registered in load_seasons()}


def test_current_season_rejects_an_unregistered_year(tmp_path):
    config = tmp_path / "seasons.yml"
    config.write_text("seasons:\n  - year: 2026\ncurrent_season: 2031\n")

    with pytest.raises(ValueError, match="not in the seasons list"):
        current_season(config)
