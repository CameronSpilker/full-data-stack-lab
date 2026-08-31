-- How well each model actually predicted, by season and game type.
--
-- Accuracy alone is a poor score for a forecaster: a model that says "the
-- favourite wins" on every game scores well and tells you nothing. So this
-- also carries the two proper scoring rules — log loss and Brier — which
-- reward a model for being confident only when it should be, and punish
-- confident mistakes far harder than hedged ones.
--
-- Read `is_point_in_time` before reading anything else in this table. A model
-- with that flag false was allowed to see the season it is predicting, so its
-- numbers are not a forecast and are not comparable to the ones that are.

with predictions as (

    select * from {{ ref('int_game_predictions') }}

),

-- Probabilities of exactly 0 or 1 make log loss infinite, so they are pulled
-- inside the interval. No model here should be producing them, and if one
-- starts to, the clamp keeps the metric readable while the tests catch it.
clamped as (

    select
        *,
        least(greatest(home_win_probability, 0.0001), 0.9999) as safe_probability,
        case when home_won then 1.0 else 0.0 end as outcome
    from predictions

),

scored as (

    select
        season,
        model_name,
        is_point_in_time,
        game_type,

        count(*) as games_scored,
        avg(case when (safe_probability > 0.5) = home_won then 1.0 else 0.0 end) as accuracy,

        -- Log loss: the average surprise, in nats. Lower is better; a coin
        -- flip on every game scores 0.693.
        -avg(
            outcome * ln(safe_probability)
            + (1 - outcome) * ln(1 - safe_probability)
        ) as log_loss,

        -- Brier score: mean squared error on the probability. 0.25 is the
        -- coin flip.
        avg(power(safe_probability - outcome, 2)) as brier_score,

        avg(abs(predicted_home_margin - actual_home_margin)) as mean_absolute_margin_error,
        avg(predicted_home_margin - actual_home_margin) as mean_margin_bias

    from clamped
    group by 1, 2, 3, 4

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['season', 'model_name', 'game_type']) }}
            as model_season_id,
        *,

        -- Against a coin flip, so a positive number is a model that beat
        -- guessing and the units are interpretable.
        1 - (brier_score / 0.25) as brier_skill_score

    from scored

)

select * from final
