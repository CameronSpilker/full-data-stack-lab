-- Every Barttorvik team must resolve to an ESPN-style team id.
--
-- This is the test that maintains the crosswalk. The two sources share no key,
-- only school names they spell differently, so an unmatched name is silent by
-- nature: the team simply vanishes from every mart that needs a rating, and
-- the dashboard looks fine. Failing the build instead, with the offending
-- names in the output, is the only way that stays visible.
--
-- To fix a failure: add the reported name to seeds/team_name_crosswalk.csv
-- with the matching ESPN `location`.

select
    season,
    rating_team_name,
    rating_conference

from {{ ref('int_team_ratings') }}
where team_id is null
