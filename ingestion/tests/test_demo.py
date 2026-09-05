from datetime import date

from ingestion import demo
from ingestion.config import load_seasons

SNAPSHOT = date(2026, 8, 30)
SEASONS = load_seasons()

# The snapshot is an offseason date, so the generator picks its own as-of date
# inside the current season. Every test that reasons about played games has to
# know which of the two it is asking about.
AS_OF = demo.as_of_date(SEASONS[-1], SNAPSHOT)


def _tables():
    return demo.extract(SEASONS, SNAPSHOT, SEASONS[-1])


def _played(games):
    return [game for game in games if game["is_completed"]]


def test_demo_generates_every_raw_table():
    tables = _tables()

    assert set(tables) == {
        "ncaa_teams",
        "ncaa_games",
        "ncaa_ratings",
        "ncaa_team_box",
        "ncaa_betting_lines",
    }
    assert all(rows for rows in tables.values())


def test_demo_is_deterministic():
    # CI, the committed warehouse, and every screenshot of the dashboard all
    # depend on this being stable run to run.
    first = _tables()["ncaa_games"]
    second = _tables()["ncaa_games"]

    assert [row["home_score"] for row in first] == [row["home_score"] for row in second]


def test_game_ids_are_unique():
    games = _tables()["ncaa_games"]

    ids = [game["game_id"] for game in games]
    assert len(set(ids)) == len(ids)


def test_no_game_ends_in_a_tie():
    # Basketball plays overtime. A tie in the source data means the generator
    # is wrong, and every win/loss aggregate downstream inherits the error.
    for game in _played(_tables()["ncaa_games"]):
        assert game["home_score"] != game["away_score"]


def test_no_team_plays_itself():
    for game in _tables()["ncaa_games"]:
        assert game["home_team_id"] != game["away_team_id"]


def test_home_teams_win_about_sixty_percent_of_the_time():
    games = [
        game for game in _played(_tables()["ncaa_games"]) if not game["is_neutral_site"]
    ]

    home_wins = sum(1 for game in games if game["home_score"] > game["away_score"])
    rate = home_wins / len(games)

    # Real Division I sits near 0.60-0.63. Synthetic data that does not
    # reproduce home advantage would make the model's home term untestable.
    assert 0.55 < rate < 0.70, f"home win rate was {rate:.3f}"


def test_every_finished_season_has_a_full_ncaa_tournament():
    # The season in progress has none: a bracket is not scheduled until the
    # regular season decides who is in it, so the generator plays those games
    # to advance the simulation and never publishes them.
    games = _tables()["ncaa_games"]

    for season in SEASONS:
        if season.end > AS_OF:
            continue
        first_round = [
            game
            for game in games
            if game["season"] == season.year
            and (game["tournament_note"] or "").endswith("First Round")
        ]
        assert len(first_round) == 32, f"{season.year} had {len(first_round)} first round games"


def test_ratings_cover_every_team_in_every_season():
    tables = _tables()
    team_names = {team["location"] for team in tables["ncaa_teams"]}

    for season in SEASONS:
        rated = {
            row["team_name"] for row in tables["ncaa_ratings"] if row["season"] == season.year
        }
        assert rated == team_names


def test_betting_lines_are_quoted_from_the_home_perspective():
    tables = _tables()
    lines = {row["game_id"]: row for row in tables["ncaa_betting_lines"]}
    games = {game["game_id"]: game for game in tables["ncaa_games"]}

    # A negative spread means the home team is favoured, so on average the
    # home team should beat a negative number more often than not.
    favoured_at_home = [
        games[game_id]["home_score"] - games[game_id]["away_score"]
        for game_id, line in lines.items()
        if line["spread"] < -5 and games[game_id]["is_completed"]
    ]
    assert sum(favoured_at_home) / len(favoured_at_home) > 0


def test_box_scores_only_cover_the_current_season():
    tables = _tables()

    seasons_with_box = {row["season"] for row in tables["ncaa_team_box"]}
    assert seasons_with_box == {SEASONS[-1].year}


def test_the_current_season_is_published_only_as_far_as_the_as_of_date():
    games = _tables()["ncaa_games"]

    for game in games:
        played = date.fromisoformat(game["game_date"]) <= AS_OF
        assert game["is_completed"] is played, game["game_date"]
        assert (game["home_score"] is not None) is played
        assert (game["away_score"] is not None) is played


def test_the_schedule_runs_past_the_as_of_date():
    # The forecast models have nothing to forecast without this, so an empty
    # schedule is a broken fixture rather than a quiet one.
    scheduled = [
        game for game in _tables()["ncaa_games"] if not game["is_completed"]
    ]

    assert len(scheduled) > 100
    assert all(date.fromisoformat(game["game_date"]) > AS_OF for game in scheduled)
    assert {game["season"] for game in scheduled} == {SEASONS[-1].year}


def test_only_the_next_few_days_of_the_schedule_are_priced():
    # Books post a line days ahead, not months. A fixture generated with a
    # line for every future game would hide the case every consumer has to
    # handle: a matchup the market has not seen.
    tables = _tables()
    games = {game["game_id"]: game for game in tables["ncaa_games"]}
    unplayed_with_a_line = [
        games[row["game_id"]]
        for row in tables["ncaa_betting_lines"]
        if not games[row["game_id"]]["is_completed"]
    ]

    assert unplayed_with_a_line
    assert all(
        (date.fromisoformat(game["game_date"]) - AS_OF).days <= demo.LINE_LEAD_DAYS
        for game in unplayed_with_a_line
    )


def test_the_as_of_date_falls_inside_the_season_either_way():
    inside = date(2026, 1, 20)
    assert demo.as_of_date(SEASONS[-1], inside) == inside

    outside = demo.as_of_date(SEASONS[-1], date(2026, 8, 30))
    assert SEASONS[-1].contains(outside)
