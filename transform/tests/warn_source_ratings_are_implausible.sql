{{ config(severity = 'warn') }}

-- Ratings the source published that this project refused to use.
--
-- collegebasketballdata.com's historical adjusted ratings contain a handful of
-- rows nothing in basketball produces: Pittsburgh 2023 at a 160.4 offensive
-- efficiency, Northwestern 2023 at a 158.1 defensive one, five teams in 2022
-- and 2023 at tempos in the thirties and forties. Staging nulls those.
--
-- A warning, not an error, and it is deliberately noisy about known bad rows.
-- The screen means the pipeline no longer breaks on them, which is exactly why
-- the count has to stay in the build log: if it climbs, the source's history
-- has moved and this project's backtests moved with it.

select
    season,
    team_id,
    rating_team_name,
    source_adjusted_offensive_efficiency,
    source_adjusted_defensive_efficiency,
    source_adjusted_tempo

from {{ ref('stg_ncaa__ratings') }}
where not has_plausible_rating
