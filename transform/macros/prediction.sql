{#
    The prediction model, defined once.

    Two marts make predictions — the matchup grid and the backtest — and they
    have to make the same one, or the accuracy numbers describe a model nobody
    is actually using. Putting the formula in a macro is what guarantees that.

    The margin is a blend of two ratings that fail differently. Adjusted
    efficiency is opponent-adjusted and stable, but it describes a whole
    season and barely moves in March. Elo is noisier and not opponent-adjusted
    beyond who you beat, but it is a time series, so it knows a team has won
    nine straight. Weighting them is in `vars`, not here.
#}

{#
    The efficiency half, on its own.

    Broken out so that a page can show what each half of the model thinks
    without recomputing it: the matchup page puts the two side by side, and a
    presentation layer that reimplemented this formula in its own SQL would be
    a second copy of the constants, which is the thing this file exists to
    prevent. `predicted_margin` below is still the only blend.
#}
{% macro efficiency_margin_component(team, opponent) %}
    (
        (
            {{ team }}.adjusted_tempo * {{ opponent }}.adjusted_tempo
            / {{ var('league_average_tempo') }}
        )
        * (
            {{ team }}.adjusted_efficiency_margin
            - {{ opponent }}.adjusted_efficiency_margin
        ) / 100.0
    )
{% endmacro %}


{# The Elo half, on its own. See the note above. #}
{% macro elo_margin_component(team, opponent) %}
    (
        ({{ team }}.elo_rating - {{ opponent }}.elo_rating)
        / {{ var('elo_points_per_rating_point') }}
    )
{% endmacro %}


{% macro predicted_margin(team, opponent, home_advantage) %}
    (
        {{ var('efficiency_model_weight') }}
            * {{ efficiency_margin_component(team, opponent) }}
        + {{ var('elo_model_weight') }}
            * {{ elo_margin_component(team, opponent) }}
        + ({{ home_advantage }})
    )
{% endmacro %}


{#
    Convert an expected margin to a win probability.

    A logistic rather than a normal CDF: the difference between the two is
    inside the noise at these sample sizes, and the logistic is what the
    betting market's own spread-to-moneyline conversion uses, which keeps the
    model and the benchmark on the same scale.
#}
{% macro margin_to_win_probability(margin) %}
    (1.0 / (1.0 + exp(-({{ margin }}) / {{ var('spread_to_probability_scale') }})))
{% endmacro %}
