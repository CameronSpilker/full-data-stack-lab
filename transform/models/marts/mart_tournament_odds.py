"""Monte Carlo simulation of the tournament, one row per team.

A bracket cannot be reasoned about one game at a time. A team's chance of
reaching the Final Four depends on who it would have to beat to get there,
which depends on who wins the other games, which is exactly the kind of
question a closed form does not answer. So the tournament is played twenty
thousand times and the answers are counted.

The simulation itself makes no predictions. Every probability it uses comes
from `mart_matchup_odds`, which is built in SQL from the shared prediction
macro. That separation is deliberate: the head-to-head page and the bracket
odds are reading the same numbers, so they cannot tell different stories about
the same game.

Vectorised across simulations rather than looped: each round is one array
operation over all twenty thousand brackets at once, which is the difference
between a model that builds in a second and one that builds in a minute.
"""

import numpy as np
import pandas as pd

# Where each seed sits in a region, top to bottom. This ordering is what makes
# a 1 seed play a 16 and puts the 1 and 2 seeds on opposite ends, so that they
# can only meet in the regional final.
BRACKET_SEED_ORDER = [1, 16, 8, 9, 5, 12, 4, 13, 6, 11, 3, 14, 7, 10, 2, 15]

ROUND_NAMES = [
    "reached_round_of_32",
    "reached_sweet_16",
    "reached_elite_eight",
    "reached_final_four",
    "reached_championship_game",
    "won_championship",
]

# Fixed, so a rebuild on unchanged data returns unchanged odds. A bracket whose
# numbers move because it was rebuilt is a bracket nobody can check.
RANDOM_SEED = 20260830


def _ordered_field(bracket: pd.DataFrame) -> pd.DataFrame:
    """Lay the field out in bracket order: region by region, seed by seed."""
    position = {seed: index for index, seed in enumerate(BRACKET_SEED_ORDER)}
    field = bracket.copy()
    field["slot"] = field["seed"].map(position)
    field = field.sort_values(["region_number", "slot"], kind="mergesort")
    return field.reset_index(drop=True)


def _probability_matrix(field: pd.DataFrame, odds: pd.DataFrame) -> np.ndarray:
    """P[i, j] is the probability team i beats team j at a neutral site."""
    index = {team_id: position for position, team_id in enumerate(field["team_id"])}
    size = len(field)

    # 0.5 is the honest default for a pair the odds table does not cover: it
    # asserts nothing. A missing pair is a data problem, and the dbt test on
    # this model's row count is what catches it.
    matrix = np.full((size, size), 0.5)

    for row in odds.itertuples(index=False):
        left = index.get(row.team_id)
        right = index.get(row.opponent_team_id)
        if left is None or right is None:
            continue
        matrix[left, right] = row.win_probability_neutral
        matrix[right, left] = 1.0 - row.win_probability_neutral

    return matrix


def model(dbt, session):
    dbt.config(materialized="table")

    simulations = int(dbt.config.get("simulations") or 20000)

    bracket = dbt.ref("mart_bracket").df()
    odds = dbt.ref("mart_matchup_odds").df()

    field = _ordered_field(bracket)
    size = len(field)

    # A partial bracket would silently produce nonsense odds, so refuse it.
    if size != 64:
        raise ValueError(
            f"mart_bracket holds {size} teams; the simulation requires exactly 64."
        )

    probability = _probability_matrix(field, odds)
    generator = np.random.default_rng(RANDOM_SEED)

    # Every simulation starts with the full field in bracket order. Each round
    # pairs adjacent survivors, which is what makes the bracket structure
    # implicit rather than something that has to be tracked.
    state = np.tile(np.arange(size), (simulations, 1))
    reached = np.zeros((len(ROUND_NAMES), size))

    for round_index in range(len(ROUND_NAMES)):
        left, right = state[:, 0::2], state[:, 1::2]
        left_wins = generator.random(left.shape) < probability[left, right]
        state = np.where(left_wins, left, right)
        reached[round_index] = np.bincount(state.ravel(), minlength=size)

    results = field[
        [
            "season",
            "team_id",
            "team_name",
            "conference_name",
            "seed",
            "region_name",
            "overall_seed",
            "bid_type",
            "record",
            "adjusted_efficiency_margin",
            "elo_rating",
            "national_rank",
        ]
    ].copy()

    for round_index, name in enumerate(ROUND_NAMES):
        results[name] = reached[round_index] / simulations

    # Expected wins is the sum of the per-round survival probabilities, and is
    # the single number that ranks a field most usefully: it rewards a team for
    # being likely to go deep, not merely for being likely to show up.
    results["expected_wins"] = results[ROUND_NAMES].sum(axis=1)
    results["simulations"] = simulations

    return results.sort_values("won_championship", ascending=False).reset_index(drop=True)
