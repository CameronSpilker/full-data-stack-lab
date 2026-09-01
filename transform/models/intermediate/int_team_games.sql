-- One row per team per game, the shape almost every downstream model wants.
--
-- A game is naturally two observations: what it says about the home team and
-- what it says about the away team. Storing it once per team means season
-- aggregates, streaks, and opponent joins are all plain group-bys instead of
-- a union written out again in every model that needs one.

with games as (

    select * from {{ ref('stg_ncaa__games') }}

),

unpivoted as (

    select
        game_id,
        season,
        game_date,
        game_type,
        tournament_round,
        is_neutral_site,
        is_conference_game,
        is_completed,
        home_team_id as team_id,
        away_team_id as opponent_team_id,
        home_team_name as team_name,
        away_team_name as opponent_name,
        home_conference_id as conference_id,
        away_conference_id as opponent_conference_id,
        home_score as points_for,
        away_score as points_against,
        home_ap_rank as ap_rank,
        away_ap_rank as opponent_ap_rank,
        not is_neutral_site as is_home,
        attendance

    from games

    union all

    select
        game_id,
        season,
        game_date,
        game_type,
        tournament_round,
        is_neutral_site,
        is_conference_game,
        is_completed,
        away_team_id as team_id,
        home_team_id as opponent_team_id,
        away_team_name as team_name,
        home_team_name as opponent_name,
        away_conference_id as conference_id,
        home_conference_id as opponent_conference_id,
        away_score as points_for,
        home_score as points_against,
        away_ap_rank as ap_rank,
        home_ap_rank as opponent_ap_rank,
        false as is_home,
        attendance

    from games

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['game_id', 'team_id']) }} as team_game_id,
        *,
        points_for - points_against as margin,

        case
            when not is_completed then null
            when points_for > points_against then true
            else false
        end as is_win,

        case
            when is_neutral_site then 'neutral'
            when is_home then 'home'
            else 'away'
        end as venue_type,

        -- Blowouts say less about team quality than the scoreboard implies, so
        -- the strength-of-schedule maths uses a capped margin. The raw margin
        -- stays available for anything that wants the real number.
        greatest(least(points_for - points_against, 20), -20) as capped_margin,

        row_number() over (
            partition by team_id, season order by game_date, game_id
        ) as game_number

    from unpivoted

)

select * from final
