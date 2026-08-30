-- Stars can drop — accounts get deleted, spam gets purged — but a week-over-week
-- fall of more than 10% is far more likely to be a bad extract than real
-- ecosystem behaviour. Fail the run so the number never reaches a dashboard.

select
    tool_name,
    week_start,
    prior_week_stars,
    stars,
    (stars - prior_week_stars) * 1.0 / prior_week_stars as star_change_rate

from {{ ref('int_repos_weekly') }}

where prior_week_stars > 0
  and (stars - prior_week_stars) * 1.0 / prior_week_stars < -0.10
