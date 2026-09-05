-- Every game still to be played this season, priced before it happens.
--
-- This is the one table in the project that cannot be checked against an
-- answer, because the answer does not exist yet. Everything else here is a
-- backtest: `mart_model_accuracy` grades predictions against results the
-- warehouse already holds. This grades nothing. It states what the model
-- thinks about games nobody has played, and it is right or wrong later.
--
-- That also makes it the only place the whole model is honestly
-- point-in-time. The backtest has to flag `blended_season_ratings` as a model
-- that saw the future, because scoring a January game with a rating that
-- describes the whole season means using March information. A game that has
-- not been played has no future to leak: every input here was measured before
-- tip-off by construction.
--
-- What it publishes, per game:
--   * the model's pick and how confident it is
--   * how often a real forecast at that confidence has actually won, from the
--     calibration table, so a number is read against its own track record
--   * where the betting market disagrees, and by how much, which is the only
--     part of this worth acting on: a pick that agrees with the price is a
--     pick that has found nothing
--   * three ranks over the games close enough to be bettable, so the
--     dashboard sorts rather than re-deriving the ordering in a page
--
-- "As of" is the last day a game was played, not the wall clock. A dashboard
-- built from a warehouse that is a day stale should say what it knows rather
-- than compute a slate against a date its data has not reached.

with season_games as (

    select * from {{ ref('stg_ncaa__games') }}
    where season = (select max(season) from {{ ref('stg_ncaa__games') }})

),

-- Not every unplayed game is an upcoming one. `scoring_status` is
-- `scheduled` whenever the source does not call a game final, and that bucket
-- holds two different things: fixtures still to come, and fixtures that came
-- and went without being played. The 2025-26 season ended carrying eighteen of
-- the second kind, fourteen postponed and four cancelled, dated between
-- November and February.
--
-- The date is what separates them, not the status text. A game whose date has
-- passed and which was never completed was abandoned, whatever the source
-- calls it, and forecasting it would put a confident pick on a game that
-- nobody is going to play.
unplayed as (

    select * from season_games
    where scoring_status = 'scheduled'

),

as_of as (

    -- Before a season tips off nothing has been played, so the reference
    -- point is the day before the first fixture rather than a null that would
    -- take every `days_out` with it.
    select coalesce(
        (select max(game_date) from season_games where is_completed),
        cast((select min(game_date) from unplayed) - interval 1 day as date)
    ) as as_of_date

),

scheduled as (

    select * from unplayed
    where game_date >= (select as_of_date from as_of)

),

forecast as (

    select * from {{ ref('int_team_forecast_inputs') }}
    where adjusted_efficiency_margin is not null
        and elo_rating is not null

),

market as (

    select * from {{ ref('int_game_market') }}

),

-- The observed win rate for real forecasts in each confidence decile. Only
-- `elo_pregame` qualifies: it is the one backtested model whose rating was
-- built without seeing the result. Reading this beside a prediction is what
-- turns "the model says 78%" into "the model says 78%, and when it has said
-- that before, it has been right this often".
track_record as (

    select
        bucket_floor_pct / 10 as bucket_index,
        observed_win_rate,
        games
    from {{ ref('mart_model_calibration') }}
    where model_name = 'elo_pregame'

),

priced as (

    select
        scheduled.game_id,
        scheduled.season,
        scheduled.game_date,
        scheduled.tipoff_at,
        scheduled.game_type,
        scheduled.is_neutral_site,
        scheduled.is_conference_game,
        scheduled.venue_name,

        (select as_of_date from as_of) as as_of_date,
        date_diff('day', (select as_of_date from as_of), scheduled.game_date)
            as days_out,

        home.team_id as home_team_id,
        home.team_name as home_team_name,
        home.conference_name as home_conference,
        home.forecast_rank as home_rank,
        home.rating_basis as home_rating_basis,
        away.team_id as away_team_id,
        away.team_name as away_team_name,
        away.conference_name as away_conference,
        away.forecast_rank as away_rank,
        away.rating_basis as away_rating_basis,

        {{ predicted_margin(
            'home', 'away',
            "case when scheduled.is_neutral_site then 0 else "
                ~ var('home_court_advantage_points') ~ " end"
        ) }} as predicted_home_margin,

        market.consensus_home_spread,
        market.market_home_win_probability,
        market.consensus_home_moneyline,
        market.consensus_away_moneyline,
        market.book_count

    from scheduled

    inner join forecast as home
        on scheduled.season = home.season and scheduled.home_team_id = home.team_id
    inner join forecast as away
        on scheduled.season = away.season and scheduled.away_team_id = away.team_id
    left join market on scheduled.game_id = market.game_id

),

sided as (

    select
        *,
        {{ margin_to_win_probability('predicted_home_margin') }}
            as home_win_probability
    from priced

),

picked as (

    select
        *,

        home_win_probability >= 0.5 as pick_is_home,

        case when home_win_probability >= 0.5
            then home_team_id else away_team_id end as pick_team_id,
        case when home_win_probability >= 0.5
            then home_team_name else away_team_name end as pick_team_name,
        case when home_win_probability >= 0.5
            then away_team_name else home_team_name end as pick_opponent_name,
        greatest(home_win_probability, 1 - home_win_probability)
            as pick_win_probability,
        abs(predicted_home_margin) as pick_margin,

        -- The market's probability for the same side, so the two numbers
        -- being compared are answers to the same question.
        case
            when market_home_win_probability is null then null
            when home_win_probability >= 0.5 then market_home_win_probability
            else 1 - market_home_win_probability
        end as market_probability_for_pick,

        case when home_win_probability >= 0.5
            then consensus_home_moneyline else consensus_away_moneyline
        end as pick_moneyline

    from sided

),

edged as (

    select
        *,

        pick_win_probability - market_probability_for_pick as edge_vs_market,

        -- An upset pick in the only sense that can be checked in advance: the
        -- model is taking the side the market has priced as the underdog.
        -- Without a line there is nothing to disagree with, so the column is
        -- null rather than false.
        case
            when market_probability_for_pick is null then null
            else market_probability_for_pick < 0.5
        end as is_market_underdog,

        -- What a dollar on the pick returns on average, at the posted price.
        -- American odds: a positive number is the profit on a dollar staked,
        -- a negative number is the stake required to profit a dollar. This is
        -- the model's own probability against the book's price, so it is only
        -- as good as the calibration on the model page says it is.
        case
            when pick_moneyline is null then null
            when pick_moneyline > 0
                then pick_win_probability * (pick_moneyline / 100.0)
                    - (1 - pick_win_probability)
            else pick_win_probability * (100.0 / abs(pick_moneyline))
                - (1 - pick_win_probability)
        end as expected_value_per_dollar

    from picked

),

with_record as (

    select
        edged.*,
        track_record.observed_win_rate as historical_win_rate_at_confidence,
        track_record.games as historical_games_at_confidence,

        -- Ranks cover the bettable window only. A game three weeks out has no
        -- line, and ranking it against tonight's card would put an unplayable
        -- fixture at the top of a list of picks. `partition by` on the same
        -- flag the `case` reads is what keeps the numbering dense: the games
        -- outside the window are numbered in their own partition and then
        -- thrown away.
        edged.days_out <= {{ var('picks_window_days') }} as in_window
    from edged
    left join track_record
        on least(floor(edged.pick_win_probability * 10), 9) = track_record.bucket_index

),

ranked as (

    select
        *,

        case when in_window then row_number() over (
            partition by in_window order by pick_win_probability desc, game_date
        ) end as confidence_rank,

        case when in_window and edge_vs_market is not null then row_number() over (
            partition by in_window and edge_vs_market is not null
            order by edge_vs_market desc, game_date
        ) end as edge_rank,

        case when in_window and is_market_underdog then row_number() over (
            partition by in_window and is_market_underdog
            order by edge_vs_market desc, game_date
        ) end as upset_rank,

        case when in_window and expected_value_per_dollar is not null then
            row_number() over (
                partition by in_window and expected_value_per_dollar is not null
                order by expected_value_per_dollar desc, game_date
            )
        end as value_rank

    from with_record

),

final as (

    select
        game_id,
        season,
        as_of_date,
        game_date,
        tipoff_at,
        days_out,
        game_type,
        is_neutral_site,
        is_conference_game,
        venue_name,

        home_team_id,
        home_team_name,
        home_conference,
        home_rank,
        home_rating_basis,
        away_team_id,
        away_team_name,
        away_conference,
        away_rank,
        away_rating_basis,

        -- The weaker of the two sides' evidence, because a matchup is only as
        -- current as the less current team in it. In November this reads
        -- `prior_season` for most of the card, which is the difference between
        -- a forecast and a guess and should not have to be inferred.
        case
            when 'prior_season' in (home_rating_basis, away_rating_basis)
                then 'prior_season'
            when 'blended' in (home_rating_basis, away_rating_basis)
                then 'blended'
            else 'current_season'
        end as forecast_basis,

        predicted_home_margin,
        home_win_probability,
        1 - home_win_probability as away_win_probability,

        pick_team_id,
        pick_team_name,
        pick_opponent_name,
        pick_is_home,
        pick_win_probability,
        pick_margin,
        historical_win_rate_at_confidence,
        historical_games_at_confidence,

        book_count,
        consensus_home_spread,
        market_home_win_probability,
        market_probability_for_pick,
        pick_moneyline,
        edge_vs_market,
        is_market_underdog,
        expected_value_per_dollar,

        confidence_rank,
        edge_rank,
        upset_rank,
        value_rank

    from ranked

)

select * from final
