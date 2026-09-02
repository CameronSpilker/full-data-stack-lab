-- No game the models treat as played ends 3-2 or 214-190.
--
-- Bad extracts rarely produce impossible structures; they produce plausible
-- structures with impossible numbers. Staging sorts those into
-- `scoring_status` and holds them out of `is_completed`, so this is the
-- regression guard on that classification: it fails if a forfeit, a
-- cancellation, or a mangled record ever reaches the models as a real game.
--
-- The bounds come from dbt_project.yml, the same place the staging model
-- reads them, so the test and the rule it checks cannot drift apart. They are
-- wide enough that a real quadruple-overtime game passes and a parsing error
-- does not.

select
    game_id,
    game_date,
    scoring_status,
    home_score,
    away_score

from {{ ref('stg_ncaa__games') }}
where is_completed
    and (
        home_score is null or away_score is null
        or least(home_score, away_score) < {{ var('plausible_score_min') }}
        or greatest(home_score, away_score) > {{ var('plausible_score_max') }}
    )
