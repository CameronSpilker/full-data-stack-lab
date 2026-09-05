-- Which season the site is describing, and which one the calendar has reached.
--
-- These come apart every November. The schedule for a new season lands weeks
-- before anyone plays in it, and almost every model here is built from results:
-- a team that has not played cannot be rated, ranked, or seeded. So the moment
-- the new schedule arrives, `mart_team_season` and everything downstream of it
-- still describe the season that finished in April, correctly, and silently.
--
-- Silently is the problem. A reader landing on a national ranking in November
-- has no way to tell it is last season's, and the dashboard would be claiming
-- something it cannot back up. One row, read by every page that shows a
-- season's numbers, so none of them can disagree about which season that is.
--
-- `data_season` is the latest season anything has been played in, which is
-- exactly what the marts key off. `schedule_season` is the latest season the
-- game feed carries at all, played or not.

with games as (

    select * from {{ ref('stg_ncaa__games') }}

),

seasons as (

    select
        max(season) as schedule_season,
        max(season) filter (where is_completed) as data_season
    from games

),

counts as (

    select
        seasons.schedule_season,
        -- Before the first game ever loaded there is nothing to describe. The
        -- coalesce keeps the row rather than letting one null take the whole
        -- banner with it.
        coalesce(seasons.data_season, seasons.schedule_season) as data_season,
        count(*) filter (
            where games.season = seasons.schedule_season and games.is_completed
        ) as completed_games,
        count(*) filter (
            where games.season = seasons.schedule_season and not games.is_completed
        ) as scheduled_games,
        min(games.game_date) filter (
            where games.season = seasons.schedule_season and not games.is_completed
        ) as next_game_date
    from seasons
    cross join games
    group by 1, 2

),

final as (

    select
        'current' as season_status_id,
        schedule_season,
        data_season,
        -- 2027 reads as 2026-27, the way every source and every reader writes it.
        cast(schedule_season - 1 as varchar) || '-'
            || right(cast(schedule_season as varchar), 2) as schedule_season_label,
        cast(data_season - 1 as varchar) || '-'
            || right(cast(data_season as varchar), 2) as data_season_label,
        schedule_season > data_season as is_preseason,
        completed_games,
        scheduled_games,
        next_game_date

    from counts

)

select * from final
