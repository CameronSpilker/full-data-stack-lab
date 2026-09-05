-- The rating each team is forecast with today, one row per team.
--
-- `int_team_prediction_inputs` describes a season. This model answers a
-- narrower question: if these two teams tip off tomorrow, what do we know
-- about them right now? Those are the same thing in March and not the same
-- thing in November, which is the problem this model exists to solve.
--
-- A rating built from four games is mostly noise, and on the opening night of
-- a season there is no rating at all: no games have been played, so there is
-- no Elo and nothing for the ratings feed to describe. Every forecast would
-- be missing on exactly the day people most want one. So a team starts the
-- season carrying what it finished the last one with, regressed toward the
-- league, and that carryover is replaced by the current season as the current
-- season earns it: full weight once a team has played
-- `forecast_settled_games`, proportional weight before that.
--
-- The regression target is the previous season's league average rather than a
-- constant, so the blend cannot drift if the rating feed rescales. The
-- carryover fraction matches the one `int_team_elo` applies between seasons,
-- because it is answering the same question about the same rosters.
--
-- `rating_basis` says which of the three cases produced each row. Nothing
-- downstream should have to guess whether a November forecast is being made
-- on this season's evidence or last season's.

with inputs as (

    select * from {{ ref('int_team_prediction_inputs') }}

),

-- The season being forecast is the one with a schedule, which is not always
-- the one with results. In November the game feed carries a season nothing
-- has been played in yet, and reading `max(season)` off the prediction inputs
-- would forecast it with last season's rows while calling them current.
target as (

    select max(season) as season from {{ ref('stg_ncaa__games') }}

),

teams as (

    select * from {{ ref('stg_ncaa__teams') }}

),

this_season as (

    select * from inputs
    where season = (select season from target)

),

prior as (

    select * from inputs
    where season = (select season - 1 from target)

),

-- What an average team looked like last season. Regressing toward this rather
-- than toward zero keeps the carryover honest if the source ever recentres
-- the ratings it publishes.
prior_league as (

    select
        avg(adjusted_efficiency_margin) as league_efficiency_margin,
        avg(adjusted_tempo) as league_tempo,
        avg(elo_rating) as league_elo
    from prior

),

carried as (

    select
        prior.team_id,
        {{ var('rating_season_carryover') }}
            * (prior.adjusted_efficiency_margin - league.league_efficiency_margin)
            + league.league_efficiency_margin as carried_efficiency_margin,
        {{ var('rating_season_carryover') }}
            * (prior.adjusted_tempo - league.league_tempo)
            + league.league_tempo as carried_tempo,
        {{ var('rating_season_carryover') }}
            * (prior.elo_rating - league.league_elo)
            + league.league_elo as carried_elo
    from prior
    cross join prior_league as league
    where prior.adjusted_efficiency_margin is not null
        and prior.elo_rating is not null

),

weighted as (

    -- Every Division I team, whether or not it has played. A team with no
    -- current-season row is the whole reason this model exists: on opening
    -- night that is all of them.
    select
        (select season from target) as season,
        teams.team_id,
        teams.team_name,
        teams.team_abbreviation,
        coalesce(this_season.conference_name, teams.conference_name) as conference_name,
        coalesce(this_season.games_played, 0) as games_played,
        coalesce(this_season.wins, 0) as wins,
        coalesce(this_season.losses, 0) as losses,

        -- Nothing about the current season is known until it is played, so the
        -- weight is the share of a settled sample the team has actually got.
        least(
            coalesce(this_season.games_played, 0)
                / cast({{ var('forecast_settled_games') }} as double),
            1.0
        ) as current_season_weight,

        this_season.adjusted_efficiency_margin as season_efficiency_margin,
        this_season.adjusted_tempo as season_tempo,
        this_season.elo_rating as season_elo,

        carried.carried_efficiency_margin,
        carried.carried_tempo,
        carried.carried_elo

    from teams
    left join this_season on teams.team_id = this_season.team_id
    left join carried on teams.team_id = carried.team_id

),

blended as (

    select
        *,

        case
            when season_efficiency_margin is null and carried_efficiency_margin is null
                then null
            when season_efficiency_margin is null then 'prior_season'
            when carried_efficiency_margin is null or current_season_weight >= 1.0
                then 'current_season'
            else 'blended'
        end as rating_basis,

        case
            when season_efficiency_margin is null then carried_efficiency_margin
            when carried_efficiency_margin is null then season_efficiency_margin
            else current_season_weight * season_efficiency_margin
                + (1 - current_season_weight) * carried_efficiency_margin
        end as adjusted_efficiency_margin,

        case
            when season_tempo is null then carried_tempo
            when carried_tempo is null then season_tempo
            else current_season_weight * season_tempo
                + (1 - current_season_weight) * carried_tempo
        end as adjusted_tempo,

        case
            when season_elo is null then carried_elo
            when carried_elo is null then season_elo
            else current_season_weight * season_elo
                + (1 - current_season_weight) * carried_elo
        end as elo_rating

    from weighted

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['season', 'team_id']) }} as team_season_id,
        season,
        team_id,
        team_name,
        team_abbreviation,
        conference_name,
        games_played,
        wins,
        losses,
        current_season_weight,
        rating_basis,
        season_efficiency_margin,
        carried_efficiency_margin,
        adjusted_efficiency_margin,
        adjusted_tempo,
        elo_rating,
        row_number() over (
            order by adjusted_efficiency_margin desc nulls last
        ) as forecast_rank

    from blended

)

select * from final
