-- Barttorvik ratings attached to ESPN team ids.
--
-- The two sources share no key, only school names they spell differently.
-- Normalisation handles the mechanical differences; the crosswalk seed handles
-- the editorial ones. Rows that match neither survive with a null team_id so
-- `assert_every_rating_matches_a_team` can name them.

with ratings as (

    select * from {{ ref('stg_torvik__ratings') }}

),

crosswalk as (

    select
        rating_team_name,
        {{ normalize_team_name('espn_team_location') }} as espn_match_key
    from {{ ref('team_name_crosswalk') }}

),

teams as (

    select * from {{ ref('stg_ncaa__teams') }}

),

resolved as (

    select
        ratings.*,
        coalesce(crosswalk.espn_match_key, ratings.team_match_key) as resolved_match_key,
        crosswalk.rating_team_name is not null as matched_via_crosswalk

    from ratings
    left join crosswalk
        on ratings.rating_team_name = crosswalk.rating_team_name

),

joined as (

    select
        resolved.* exclude (resolved_match_key),
        teams.team_id,
        teams.team_name,
        teams.conference_id,
        teams.conference_name

    from resolved
    left join teams
        on resolved.resolved_match_key = teams.team_match_key

)

select * from joined
