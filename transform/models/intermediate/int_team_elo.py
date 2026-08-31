"""Elo ratings, computed one game at a time in chronological order.

Every other model in this project is SQL, and should be. This one is not,
because Elo is irreducibly sequential: a team's rating going into a game
depends on the result of the game before it, for both teams. Expressed in SQL
that is a recursive CTE whose depth is the number of games in the dataset —
tens of thousands — which DuckDB will either refuse or crawl through. A loop
in Python is the honest shape of the computation, so it is written as one.

What Elo adds over the adjusted efficiency ratings the pipeline already has:
it is a time series. Barttorvik publishes what a team looks like now; Elo says
what it looked like in January, which is what makes a backtest possible at all.
The two are complements, and the marts use both.
"""

import pandas as pd

# Elo starts everyone level. The scale is conventional: 400 points is a 10:1
# odds ratio, which is what makes the logistic below the standard form.
INITIAL_ELO = 1500.0

# How far a single result can move a rating. 20 is typical for a long season
# where ratings should settle; 32 is chess's classic value and moves faster
# than a 30-game season warrants.
K_FACTOR = 20.0

# Home court in college basketball is worth roughly 3.5 points, and the usual
# points-to-Elo conversion is about 25 Elo per point.
HOME_ADVANTAGE_ELO = 70.0

# Rosters turn over every year, so a rating carries forward only partly.
# 0.75 keeps three quarters of a team's distance from average.
SEASON_CARRYOVER = 0.75


def _win_probability(rating: float, opponent_rating: float) -> float:
    """The standard Elo logistic: 400 points is 10:1."""
    return 1.0 / (1.0 + 10.0 ** ((opponent_rating - rating) / 400.0))


def _margin_multiplier(margin: int, winner_rating_edge: float) -> float:
    """Scale the update by margin of victory.

    A one-point win and a thirty-point win are not the same evidence, but the
    relationship is concave — the thirtieth point says much less than the
    fifth. The denominator is the standard correction for autocorrelation:
    without it, strong teams run away with the ratings, because they are the
    ones who win big and are then rewarded twice for it.
    """
    return ((abs(margin) + 3.0) ** 0.8) / (7.5 + 0.006 * winner_rating_edge)


def model(dbt, session):
    dbt.config(materialized="table")

    games = dbt.ref("stg_ncaa__games").df()
    games = games[games["is_completed"].fillna(False).astype(bool)]
    games = games.dropna(subset=["home_score", "away_score"])
    games = games.sort_values(["game_date", "game_id"], kind="mergesort")

    ratings: dict[str, float] = {}
    current_season = None
    records = []

    for game in games.itertuples(index=False):
        # Between seasons every rating regresses toward the mean. Without this
        # a program that was good in 2022 starts 2026 good regardless of who
        # is on the roster.
        if current_season is not None and game.season != current_season:
            ratings = {
                team_id: INITIAL_ELO + SEASON_CARRYOVER * (rating - INITIAL_ELO)
                for team_id, rating in ratings.items()
            }
        current_season = game.season

        home_id, away_id = game.home_team_id, game.away_team_id
        home_before = ratings.get(home_id, INITIAL_ELO)
        away_before = ratings.get(away_id, INITIAL_ELO)

        advantage = 0.0 if game.is_neutral_site else HOME_ADVANTAGE_ELO
        home_expected = _win_probability(home_before + advantage, away_before)

        margin = int(game.home_score) - int(game.away_score)
        home_won = margin > 0
        home_actual = 1.0 if home_won else 0.0

        winner_edge = (
            (home_before + advantage) - away_before
            if home_won
            else away_before - (home_before + advantage)
        )
        change = K_FACTOR * _margin_multiplier(margin, winner_edge) * (
            home_actual - home_expected
        )

        home_after = home_before + change
        away_after = away_before - change
        ratings[home_id] = home_after
        ratings[away_id] = away_after

        for team_id, opponent_id, before, after, opponent_before, expected, is_home in (
            (home_id, away_id, home_before, home_after, away_before, home_expected, True),
            (away_id, home_id, away_before, away_after, home_before, 1 - home_expected, False),
        ):
            records.append(
                {
                    "season": game.season,
                    "game_id": game.game_id,
                    "game_date": game.game_date,
                    "game_type": game.game_type,
                    "team_id": team_id,
                    "opponent_team_id": opponent_id,
                    "is_home": is_home,
                    "is_neutral_site": bool(game.is_neutral_site),
                    "elo_before": before,
                    "elo_after": after,
                    "opponent_elo_before": opponent_before,
                    "pregame_win_probability": expected,
                    "margin": margin if is_home else -margin,
                    "is_win": home_won if is_home else not home_won,
                }
            )

    frame = pd.DataFrame.from_records(records)
    frame["elo_change"] = frame["elo_after"] - frame["elo_before"]
    frame["game_number"] = (
        frame.sort_values(["game_date", "game_id"], kind="mergesort")
        .groupby(["season", "team_id"])
        .cumcount()
        + 1
    )
    return frame
