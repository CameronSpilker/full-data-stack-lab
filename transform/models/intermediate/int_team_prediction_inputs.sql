-- Everything the predictor needs about a team, one row per team per season.
--
-- The marts join this to itself to build a matchup, so anything a prediction
-- depends on has to be here. Teams missing an efficiency rating are kept with
-- nulls rather than dropped: a matchup that cannot be predicted should be
-- visibly absent downstream, not silently missing a row.
--
-- Division I only. Every opponent a Division I side played appears in the game
-- data, and roughly 350 of them are the November buy-game and exhibition
-- opponents that fill out a non-conference schedule: NAIA schools, Bible
-- colleges, a few Division III programmes. Those games count for the Division
-- I side and belong in its strength of schedule, which is why
-- `int_team_season_form` still rates them. They are not teams this project
-- tracks, so they stop here rather than turning up in national ranks and in a
-- "teams tracked" figure of 716.

with form as (

    select * from {{ ref('int_team_season_form') }}

),

ratings as (

    select * from {{ ref('int_team_ratings') }}
    where team_id is not null

),

teams as (

    select * from {{ ref('stg_ncaa__teams') }}

),

final_elo as (

    -- The rating after a team's most recent game is its current rating.
    select
        season,
        team_id,
        elo_after as elo_rating
    from {{ ref('int_team_elo') }}
    qualify
        row_number() over (
            partition by season, team_id order by game_date desc, game_id desc
        ) = 1

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['form.season', 'form.team_id']) }}
            as team_season_id,
        form.season,
        form.team_id,
        teams.team_name,
        teams.team_location,
        teams.team_abbreviation,
        -- The dimension holds one conference per team, from the latest
        -- snapshot, so a past season falls back to what the rating said the
        -- team's league was at the time.
        coalesce(teams.conference_name, ratings.rating_conference) as conference_name,
        teams.conference_id,

        form.games_played,
        form.wins,
        form.losses,
        form.win_pct,
        form.conference_wins,
        form.conference_losses,
        form.avg_margin,
        form.avg_points_for,
        form.avg_points_against,
        form.srs_rating,
        form.srs_rank,
        form.strength_of_schedule,
        form.wins_vs_top_50,
        form.games_vs_top_50,
        form.last_10_wins,
        form.last_10_games,
        form.last_10_avg_margin,

        ratings.adjusted_offensive_efficiency,
        ratings.adjusted_defensive_efficiency,
        ratings.adjusted_efficiency_margin,
        ratings.adjusted_tempo,
        ratings.effective_fg_pct,
        ratings.effective_fg_pct_allowed,
        ratings.turnover_pct,
        ratings.turnover_pct_forced,
        ratings.offensive_rebound_pct,
        ratings.defensive_rebound_pct,
        ratings.free_throw_rate,
        ratings.two_point_pct,
        ratings.three_point_pct,

        elo.elo_rating,

        row_number() over (
            partition by form.season order by ratings.adjusted_efficiency_margin desc
        ) as efficiency_rank,
        row_number() over (
            partition by form.season order by elo.elo_rating desc
        ) as elo_rank

    from form

    -- The one inner join in the model, and the Division I filter: a team the
    -- dimension does not carry is an opponent, not a subject.
    join teams
        on form.team_id = teams.team_id

    left join ratings
        on form.season = ratings.season and form.team_id = ratings.team_id

    left join final_elo as elo
        on form.season = elo.season and form.team_id = elo.team_id

)

select * from final
