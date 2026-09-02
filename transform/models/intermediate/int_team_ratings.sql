-- Ratings attached to the team dimension.
--
-- Both sides come from collegebasketballdata.com and share a team id, so this
-- is an equi-join on a key rather than a match on school names spelled
-- differently. That is the whole reason the rating source moved: the old join
-- went through a normalisation macro and a hand-maintained crosswalk seed, and
-- every new team that appeared was a build failure until someone added a row.

with ratings as (

    select * from {{ ref('stg_ncaa__ratings') }}

),

teams as (

    select * from {{ ref('stg_ncaa__teams') }}

),

joined as (

    select
        ratings.*,
        teams.team_id is not null as matched_a_team,
        teams.team_name,
        teams.conference_id,
        teams.conference_name

    from ratings
    left join teams
        on ratings.team_id = teams.team_id

)

select * from joined
