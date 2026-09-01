-- A team cannot play itself.
--
-- Cheap, and it catches the single most damaging join error available here:
-- if team ids were ever mismatched between the game feed and the dimension,
-- self-matchups are the first thing that appears.

select game_id, home_team_id
from {{ ref('stg_ncaa__games') }}
where home_team_id = away_team_id
