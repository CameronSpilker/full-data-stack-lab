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
--
-- A season the rating source has not published yet borrows the last one. The
-- source publishes a week or two after a season tips off, and until it does
-- every efficiency column for the new season would be null: no national rank,
-- no offence or defence, nothing for a page to draw. So for a season with no
-- published ratings at all, each team carries what it finished the previous
-- season with, pulled toward that season's league average by
-- `rating_season_carryover`, the same regression `int_team_forecast_inputs`
-- and `int_team_elo` apply between seasons. Elo is untouched: it is built from
-- this season's results and moves with every game.
--
-- `rating_basis` says which a row is: 'published', 'carried', or null where
-- neither exists. Only a season with no ratings at all is carried. A team
-- missing from a season the source did publish stays null, as before.

with form as (

    select * from {{ ref('int_team_season_form') }}

),

published as (

    select * from {{ ref('int_team_ratings') }}
    where team_id is not null

),

published_seasons as (

    select distinct season from published

),

-- What an average team looked like in each published season, the point a
-- carried rating is regressed toward.
league as (

    select
        season,
        avg(adjusted_offensive_efficiency) as offensive_efficiency,
        avg(adjusted_defensive_efficiency) as defensive_efficiency,
        avg(adjusted_efficiency_margin) as efficiency_margin,
        avg(adjusted_tempo) as tempo,
        avg(effective_fg_pct) as effective_fg_pct,
        avg(effective_fg_pct_allowed) as effective_fg_pct_allowed,
        avg(turnover_pct) as turnover_pct,
        avg(turnover_pct_forced) as turnover_pct_forced,
        avg(offensive_rebound_pct) as offensive_rebound_pct,
        avg(defensive_rebound_pct) as defensive_rebound_pct,
        avg(free_throw_rate) as free_throw_rate,
        avg(two_point_pct) as two_point_pct,
        avg(three_point_pct) as three_point_pct
    from published
    group by season

),

{%- set carried_columns = [
    ('adjusted_offensive_efficiency', 'offensive_efficiency'),
    ('adjusted_defensive_efficiency', 'defensive_efficiency'),
    ('adjusted_efficiency_margin', 'efficiency_margin'),
    ('adjusted_tempo', 'tempo'),
    ('effective_fg_pct', 'effective_fg_pct'),
    ('effective_fg_pct_allowed', 'effective_fg_pct_allowed'),
    ('turnover_pct', 'turnover_pct'),
    ('turnover_pct_forced', 'turnover_pct_forced'),
    ('offensive_rebound_pct', 'offensive_rebound_pct'),
    ('defensive_rebound_pct', 'defensive_rebound_pct'),
    ('free_throw_rate', 'free_throw_rate'),
    ('two_point_pct', 'two_point_pct'),
    ('three_point_pct', 'three_point_pct'),
] %}

-- Last season's ratings, regressed, for every season that has results but
-- no published ratings of its own.
carried as (

    select
        seasons.season,
        prior.team_id,
        prior.rating_conference,
        {%- for column, league_column in carried_columns %}
        {{ var('rating_season_carryover') }}
            * (prior.{{ column }} - league.{{ league_column }})
            + league.{{ league_column }} as {{ column }},
        {%- endfor %}
        'carried' as rating_basis
    from (select distinct season from form) as seasons
    join published as prior
        on prior.season = seasons.season - 1
    join league
        on league.season = prior.season
    where seasons.season not in (select season from published_seasons)

),

ratings as (

    select
        season,
        team_id,
        rating_conference,
        {%- for column, _ in carried_columns %}
        {{ column }},
        {%- endfor %}
        'published' as rating_basis
    from published

    union all

    select * from carried

),

teams as (

    select * from {{ ref('stg_ncaa__teams') }}

),

secondary_colors as (

    select * from {{ ref('team_secondary_colors') }}

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
        -- Identity rather than measurement: carried this far so a page can
        -- draw a team without joining back to the dimension itself.
        teams.team_logo_url,
        teams.team_color,
        secondary_colors.team_secondary_color,

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
        ratings.rating_basis,

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

    left join secondary_colors
        on form.team_id = secondary_colors.team_id

)

select * from final
