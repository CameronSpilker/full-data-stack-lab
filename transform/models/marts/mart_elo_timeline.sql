-- Elo after every game, for charting a team's season as it happened.
--
-- This is the only rating in the project that is a genuine time series, which
-- makes it the only one that can answer "when did this team turn its season
-- around" rather than just "how good were they overall".

with elo as (

    select * from {{ ref('int_team_elo') }}

),

teams as (

    select season, team_id, team_name, conference_name from {{ ref('mart_team_season') }}

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['elo.game_id', 'elo.team_id']) }}
            as team_game_id,
        elo.season,
        elo.team_id,
        teams.team_name,
        teams.conference_name,
        elo.game_id,
        elo.game_date,
        elo.game_number,
        elo.game_type,
        elo.opponent_team_id,
        opponents.team_name as opponent_name,
        elo.is_home,
        elo.is_neutral_site,
        elo.is_win,
        elo.margin,
        elo.elo_before,
        elo.elo_after,
        elo.elo_change,
        elo.opponent_elo_before,
        elo.pregame_win_probability,

        -- A win the model gave you less than a 25% chance of is the kind of
        -- result that decides a bracket.
        elo.is_win and elo.pregame_win_probability < 0.25 as was_upset_win

    from elo
    left join teams
        on elo.season = teams.season and elo.team_id = teams.team_id
    left join teams as opponents
        on elo.season = opponents.season and elo.opponent_team_id = opponents.team_id

)

select * from final
