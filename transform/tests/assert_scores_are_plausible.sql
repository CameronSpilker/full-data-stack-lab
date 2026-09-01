-- A completed Division I game does not end 3-2 or 214-190.
--
-- Bad extracts rarely produce impossible structures; they produce plausible
-- structures with impossible numbers. The bounds are wide enough that a real
-- quadruple-overtime game passes and a parsing error does not.

select
    game_id,
    game_date,
    home_score,
    away_score

from {{ ref('stg_ncaa__games') }}
where is_completed
    and (
        home_score < 20 or away_score < 20
        or home_score > 200 or away_score > 200
    )
