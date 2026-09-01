-- Any model that claims to forecast must beat guessing, overall.
--
-- A coin flip scores a log loss of 0.693. A model above that is worse than
-- useless, and because the marts present these numbers as evidence the
-- predictor works, the claim is worth asserting rather than eyeballing.
--
-- Pooled across seasons and game types on purpose. An earlier version of this
-- test asserted the same thing of every slice and failed on one season's
-- conference tournaments — 224 games between teams from the same league, at
-- neutral sites, which really are close to coin flips. That was the test being
-- wrong about what the claim is, not the model being broken. The slice-level
-- version survives as a warning in
-- `warn_model_slices_below_a_coin_flip.sql`.
--
-- Only point-in-time models are checked. The blended model is scored against
-- ratings that postdate the games it predicts, so passing this would prove
-- nothing about it.

with pooled as (

    select
        model_name,
        sum(games_scored) as games_scored,
        sum(log_loss * games_scored) / nullif(sum(games_scored), 0) as log_loss

    from {{ ref('mart_model_accuracy') }}
    where is_point_in_time
    group by 1

)

select *
from pooled
where games_scored >= 100
    and log_loss >= 0.693
