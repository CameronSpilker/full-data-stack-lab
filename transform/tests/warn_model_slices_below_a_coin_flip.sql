{{ config(severity = 'warn') }}

-- Which slices a forecasting model does no better than guessing on.
--
-- A warning rather than an error, because this is a finding and not a defect.
-- Some slices genuinely are coin flips: conference tournament games pit teams
-- from the same league against each other at neutral sites, which strips out
-- most of the signal a rating has. Seeing that surface is useful. Failing a
-- build over it would only train someone to stop reading the output.

select
    model_name,
    season,
    game_type,
    games_scored,
    log_loss,
    accuracy

from {{ ref('mart_model_accuracy') }}
where is_point_in_time
    and games_scored >= 100
    and log_loss >= 0.693
