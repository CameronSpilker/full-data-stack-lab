{{ config(severity = 'warn') }}

-- Seasons where an unusual share of finished games was held out as not
-- actually played.
--
-- Staging drops forfeits, cancellations, and mangled scorelines out of
-- `is_completed`. That is correct and it is also invisible: a season quietly
-- loses games and every downstream rate keeps computing. This puts a number
-- on it, per season, so the exclusions stay something someone chose rather
-- than something that happened.
--
-- A warning, not an error. Real seasons carry a few: 2022 and 2023 have
-- seventeen COVID forfeits between them, which is about a quarter of one
-- percent. Two percent would mean the source changed shape, and that is worth
-- a build reading the rows.

with by_season as (

    select
        season,
        count(*) as finished_games,
        count(*) filter (where not is_completed) as held_out,
        count(*) filter (where scoring_status = 'forfeit') as forfeits,
        count(*) filter (where scoring_status = 'not_played') as cancellations,
        count(*) filter (where scoring_status in ('unrecorded', 'implausible'))
            as bad_records

    from {{ ref('stg_ncaa__games') }}
    where source_says_completed
    group by 1

)

select
    *,
    held_out * 1.0 / nullif(finished_games, 0) as held_out_share

from by_season
where held_out > finished_games * 0.02
