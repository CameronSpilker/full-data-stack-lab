-- The game log, enriched with what each model thought beforehand.
--
-- One row per game, not per team: this is the browsable record of what
-- happened, and a game is one event even though two teams played in it.

with games as (

    select * from {{ ref('stg_ncaa__games') }}

),

teams as (

    select season, team_id, team_name, conference_name, national_rank
    from {{ ref('mart_team_season') }}

),

market as (

    select * from {{ ref('int_game_market') }}

),

elo as (

    select
        game_id,
        elo_before as home_elo_before,
        opponent_elo_before as away_elo_before,
        pregame_win_probability as elo_home_win_probability
    from {{ ref('int_team_elo') }}
    where is_home

),

final as (

    select
        games.game_id,
        games.season,
        games.game_date,
        games.game_type,
        games.tournament_round,
        games.is_neutral_site,
        games.is_conference_game,
        games.is_completed,
        games.venue_name,
        games.attendance,

        games.home_team_id,
        coalesce(home.team_name, games.home_team_name) as home_team_name,
        home.conference_name as home_conference,
        home.national_rank as home_national_rank,
        games.home_score,

        games.away_team_id,
        coalesce(away.team_name, games.away_team_name) as away_team_name,
        away.conference_name as away_conference,
        away.national_rank as away_national_rank,
        games.away_score,

        games.home_margin,
        games.total_points,
        games.winning_team_id,

        elo.home_elo_before,
        elo.away_elo_before,
        elo.elo_home_win_probability,

        market.consensus_home_spread,
        market.consensus_over_under,
        market.market_home_win_probability,
        market.book_count,

        -- Did the home team beat the number? Positive means they covered.
        case
            when market.consensus_home_spread is not null and games.is_completed
                then games.home_margin + market.consensus_home_spread
        end as home_cover_margin,

        -- An upset is the lower-rated team winning. Ranked by Elo because it
        -- is the only rating that was knowable before tip-off.
        case
            when games.is_completed and elo.home_elo_before is not null
                then (games.home_margin > 0) != (elo.home_elo_before > elo.away_elo_before)
        end as was_upset

    from games

    left join teams as home
        on games.season = home.season and games.home_team_id = home.team_id
    left join teams as away
        on games.season = away.season and games.away_team_id = away.team_id
    left join market on games.game_id = market.game_id
    left join elo on games.game_id = elo.game_id

)

select * from final
