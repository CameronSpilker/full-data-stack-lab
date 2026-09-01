-- Every possible matchup in the current season, priced at a neutral site.
--
-- Precomputing the whole grid rather than calculating on demand is what makes
-- the tournament simulation a lookup instead of a model: the simulator draws
-- from this table, so the bracket odds and the head-to-head page can never
-- disagree about the same game.
--
-- Neutral site, because that is where the tournament is played. The home
-- advantage is still available as a column for anyone pricing a regular
-- season game.

with inputs as (

    select * from {{ ref('int_team_prediction_inputs') }}
    where season = (select max(season) from {{ ref('int_team_prediction_inputs') }})
        and adjusted_efficiency_margin is not null
        and elo_rating is not null

),

pairs as (

    select
        team.season,
        team.team_id,
        team.team_name,
        team.conference_name,
        opponent.team_id as opponent_team_id,
        opponent.team_name as opponent_name,
        opponent.conference_name as opponent_conference,

        {{ predicted_margin('team', 'opponent', 0) }} as neutral_margin,
        {{ predicted_margin(
            'team', 'opponent', var('home_court_advantage_points')
        ) }} as home_margin

    from inputs as team
    inner join inputs as opponent
        on team.season = opponent.season
        and team.team_id < opponent.team_id

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['team_id', 'opponent_team_id']) }}
            as matchup_id,
        season,
        team_id,
        team_name,
        conference_name,
        opponent_team_id,
        opponent_name,
        opponent_conference,

        neutral_margin as predicted_margin_neutral,
        home_margin as predicted_margin_at_home,

        {{ margin_to_win_probability('neutral_margin') }} as win_probability_neutral,
        {{ margin_to_win_probability('home_margin') }} as win_probability_at_home

    from pairs

)

select * from final
