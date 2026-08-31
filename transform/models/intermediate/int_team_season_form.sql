-- Season-to-date form for every team: record, splits, recent play, and a
-- strength of schedule computed from results alone.
--
-- The strength-of-schedule figure is a Simple Rating System: a team's rating
-- is its average margin plus the average rating of everyone it played. That is
-- circular by definition, so it is solved by iteration — start from raw margin
-- and substitute the previous pass in a fixed number of times. Three passes is
-- well inside the point where the ordering stops moving.
--
-- This deliberately duplicates work Barttorvik already does. It is the control:
-- a rating built only from this project's own game data, so a break in the
-- ratings feed shows up as a divergence rather than as silence.

{% set srs_iterations = 3 %}

with team_games as (

    select * from {{ ref('int_team_games') }}
    where is_completed

),

base as (

    select
        season,
        team_id,
        max(team_name) as team_name,
        max(conference_id) as conference_id,
        count(*) as games_played,
        sum(case when is_win then 1 else 0 end) as wins,
        sum(case when is_win then 0 else 1 end) as losses,
        avg(capped_margin) as avg_capped_margin,
        avg(margin) as avg_margin,
        avg(points_for) as avg_points_for,
        avg(points_against) as avg_points_against,

        sum(case when is_conference_game and is_win then 1 else 0 end) as conference_wins,
        sum(case when is_conference_game and not is_win then 1 else 0 end) as conference_losses,

        sum(case when venue_type = 'home' and is_win then 1 else 0 end) as home_wins,
        sum(case when venue_type = 'home' and not is_win then 1 else 0 end) as home_losses,
        sum(case when venue_type = 'away' and is_win then 1 else 0 end) as away_wins,
        sum(case when venue_type = 'away' and not is_win then 1 else 0 end) as away_losses,
        sum(case when venue_type = 'neutral' and is_win then 1 else 0 end) as neutral_wins,
        sum(case when venue_type = 'neutral' and not is_win then 1 else 0 end) as neutral_losses

    from team_games
    group by 1, 2

),

rating_0 as (

    select season, team_id, avg_capped_margin as rating from base

),

{% for iteration in range(1, srs_iterations + 1) %}
rating_{{ iteration }} as (

    select
        base.season,
        base.team_id,
        base.avg_capped_margin + coalesce(opponents.avg_opponent_rating, 0) as rating,
        opponents.avg_opponent_rating

    from base

    left join (
        select
            team_games.season,
            team_games.team_id,
            avg(prior.rating) as avg_opponent_rating
        from team_games
        inner join rating_{{ iteration - 1 }} as prior
            on team_games.season = prior.season
            and team_games.opponent_team_id = prior.team_id
        group by 1, 2
    ) as opponents
        on base.season = opponents.season
        and base.team_id = opponents.team_id

),
{% endfor %}

recent as (

    select
        season,
        team_id,
        count(*) as last_10_games,
        sum(case when is_win then 1 else 0 end) as last_10_wins,
        avg(margin) as last_10_avg_margin

    from (
        select
            *,
            row_number() over (
                partition by season, team_id order by game_date desc, game_id desc
            ) as recency
        from team_games
    )
    where recency <= 10
    group by 1, 2

),

ranked as (

    select
        season,
        team_id,
        rating,
        row_number() over (partition by season order by rating desc) as srs_rank
    from rating_{{ srs_iterations }}

),

quality as (

    -- Beating a top-50 team is the signal a selection committee actually
    -- weighs, and it is the cheapest available proxy for a Quadrant 1 win.
    select
        team_games.season,
        team_games.team_id,
        sum(case when ranked.srs_rank <= 50 and team_games.is_win then 1 else 0 end)
            as wins_vs_top_50,
        sum(case when ranked.srs_rank <= 50 then 1 else 0 end) as games_vs_top_50

    from team_games
    inner join ranked
        on team_games.season = ranked.season
        and team_games.opponent_team_id = ranked.team_id
    group by 1, 2

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['base.season', 'base.team_id']) }}
            as team_season_id,
        base.season,
        base.team_id,
        base.team_name,
        base.conference_id,
        base.games_played,
        base.wins,
        base.losses,
        base.wins * 1.0 / nullif(base.games_played, 0) as win_pct,
        base.conference_wins,
        base.conference_losses,
        base.home_wins,
        base.home_losses,
        base.away_wins,
        base.away_losses,
        base.neutral_wins,
        base.neutral_losses,
        base.avg_margin,
        base.avg_points_for,
        base.avg_points_against,

        rating.rating as srs_rating,
        rating.avg_opponent_rating as strength_of_schedule,
        ranked.srs_rank,

        coalesce(quality.wins_vs_top_50, 0) as wins_vs_top_50,
        coalesce(quality.games_vs_top_50, 0) as games_vs_top_50,

        recent.last_10_games,
        recent.last_10_wins,
        recent.last_10_avg_margin

    from base

    inner join rating_{{ srs_iterations }} as rating
        on base.season = rating.season and base.team_id = rating.team_id

    inner join ranked
        on base.season = ranked.season and base.team_id = ranked.team_id

    left join recent
        on base.season = recent.season and base.team_id = recent.team_id

    left join quality
        on base.season = quality.season and base.team_id = quality.team_id

)

select * from final
