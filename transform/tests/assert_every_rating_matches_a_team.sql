-- Every rated team must exist in the team dimension.
--
-- Ratings and teams now come from the same source and share a team id, so this
-- should hold by construction. It is kept because "should hold by construction"
-- is exactly the assumption worth testing: a rated team missing from the
-- dimension would vanish from every mart that needs a rating, and the
-- dashboard would look fine while quietly dropping teams.
--
-- Before the rating source moved, this test maintained a hand-written
-- crosswalk between two sources that shared no key. That crosswalk is gone.

select
    season,
    team_id,
    rating_team_name,
    rating_conference

from {{ ref('int_team_ratings') }}
where not matched_a_team
