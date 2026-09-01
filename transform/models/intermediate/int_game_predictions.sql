-- Every completed game, scored by every model, in one long table.
--
-- The `is_point_in_time` flag is the important column here, and it is the
-- reason the models are stacked rather than sitting in columns side by side.
--
-- Elo is honest by construction: its pregame rating was computed from games
-- that had already happened, so scoring a game with it is a real prediction.
-- The blended model is not, yet. Barttorvik publishes a rating that describes
-- the whole season, so using it to "predict" a January game means using March
-- information — the model is being told the answer. Its accuracy will look
-- excellent and mean nothing.
--
-- Both are kept because both are useful, but a chart that puts them on the
-- same axis without saying which is which is a lie. Downstream models carry
-- the flag through, and the dashboard separates them on it.
--
-- This resolves as history accumulates: the ratings table is snapshotted by
-- date, so once the pipeline has run through a season, a point-in-time
-- efficiency rating exists and the blended model can be scored honestly too.

with games as (

    select * from {{ ref('stg_ncaa__games') }}
    where is_completed
        and home_score is not null
        and away_score is not null

),

elo as (

    -- The home team's row carries the pregame probability for the game.
    select
        game_id,
        pregame_win_probability as home_win_probability,
        (elo_before + case when is_neutral_site then 0 else {{ var('home_court_advantage_points') }} * {{ var('elo_points_per_rating_point') }} end
            - opponent_elo_before) / {{ var('elo_points_per_rating_point') }} as predicted_home_margin
    from {{ ref('int_team_elo') }}
    where is_home

),

market as (

    select * from {{ ref('int_game_market') }}

),

inputs as (

    select * from {{ ref('int_team_prediction_inputs') }}

),

blended as (

    select
        games.game_id,
        {{ predicted_margin(
            'home', 'away',
            "case when games.is_neutral_site then 0 else "
                ~ var('home_court_advantage_points') ~ " end"
        ) }} as predicted_home_margin

    from games
    inner join inputs as home
        on games.season = home.season and games.home_team_id = home.team_id
    inner join inputs as away
        on games.season = away.season and games.away_team_id = away.team_id
    where home.adjusted_efficiency_margin is not null
        and away.adjusted_efficiency_margin is not null
        and home.elo_rating is not null
        and away.elo_rating is not null

),

scored as (

    select
        games.season,
        games.game_id,
        games.game_date,
        games.game_type,
        games.home_team_id,
        games.away_team_id,
        games.home_margin as actual_home_margin,
        games.home_score > games.away_score as home_won,

        'elo_pregame' as model_name,
        true as is_point_in_time,
        elo.home_win_probability,
        elo.predicted_home_margin

    from games
    inner join elo on games.game_id = elo.game_id

    union all

    select
        games.season,
        games.game_id,
        games.game_date,
        games.game_type,
        games.home_team_id,
        games.away_team_id,
        games.home_margin,
        games.home_score > games.away_score,

        'market_consensus',
        true,
        market.market_home_win_probability,
        market.market_home_margin

    from games
    inner join market on games.game_id = market.game_id

    union all

    select
        games.season,
        games.game_id,
        games.game_date,
        games.game_type,
        games.home_team_id,
        games.away_team_id,
        games.home_margin,
        games.home_score > games.away_score,

        'blended_season_ratings',
        false,
        {{ margin_to_win_probability('blended.predicted_home_margin') }},
        blended.predicted_home_margin

    from games
    inner join blended on games.game_id = blended.game_id

)

select * from scored
