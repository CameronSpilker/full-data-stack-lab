-- Which season the site is describing, which one the calendar has reached, and
-- whether there is anything left to play.
--
-- These come apart twice a year, and in two different ways.
--
-- Every November the schedule for a new season lands weeks before anyone plays
-- in it. Almost every model here is built from results: a team that has not
-- played cannot be rated, ranked, or seeded. So the moment the new schedule
-- arrives, `mart_team_season` and everything downstream of it still describe
-- the season that finished in April, correctly, and silently. That is the
-- preseason.
--
-- Every April the opposite happens. The last game is played, the schedule for
-- the next season does not exist yet, and the forecast has nothing to price.
-- `mart_upcoming_games` is empty, not broken, and a page that draws a chart
-- from it draws an empty chart. That is the offseason, and it is the longer of
-- the two: roughly seven months of the year.
--
-- Silently is the problem in both. A reader landing on a national ranking in
-- November has no way to tell it is last season's, and a reader landing on an
-- empty forecast in July cannot tell a quiet season from a broken pipeline. One
-- row, read by every page, so none of them can disagree about which season they
-- are showing or why a table is empty.
--
-- `data_season` is the latest season anything has been played in, which is
-- exactly what the marts key off. `schedule_season` is the latest season the
-- game feed carries at all, played or not. `phase` is the one column a page
-- should switch on.

with games as (

    select * from {{ ref('stg_ncaa__games') }}

),

seasons as (

    select
        max(season) as schedule_season,
        max(season) filter (where is_completed) as data_season
    from games

),

schedule_season_games as (

    select games.*
    from games
    cross join seasons
    where games.season = seasons.schedule_season

),

-- The reference date, defined exactly as `mart_upcoming_games` defines it, so
-- the two cannot disagree about which fixtures are still ahead. Before a season
-- tips off nothing has been played, so it falls back to the day before the
-- first fixture rather than a null that would take the comparison with it.
as_of as (

    select coalesce(
        (select max(game_date) from schedule_season_games where is_completed),
        cast(
            (select min(game_date) from schedule_season_games where not is_completed)
                - interval 1 day
            as date
        )
    ) as as_of_date

),

-- Not every unplayed fixture is an upcoming one. `is_completed` is false
-- whenever the source does not call a game final, and that bucket holds two
-- different things: fixtures still to come, and fixtures that came and went
-- without being played. The 2025-26 season ended carrying eighteen of the
-- second kind, fourteen postponed and four cancelled.
--
-- The date is what separates them. Counting the abandoned ones as upcoming
-- would leave the site claiming a season is still running seven months after
-- its final, and pointing at a "next game" that happened in November.
counts as (

    select
        seasons.schedule_season,
        -- Before the first game ever loaded there is nothing to describe. The
        -- coalesce keeps the row rather than letting one null take the whole
        -- banner with it.
        coalesce(seasons.data_season, seasons.schedule_season) as data_season,
        count(*) filter (where schedule_season_games.is_completed) as completed_games,
        count(*) filter (where not schedule_season_games.is_completed) as unplayed_games,
        count(*) filter (
            where not schedule_season_games.is_completed
                and schedule_season_games.game_date >= as_of.as_of_date
        ) as upcoming_games,
        min(schedule_season_games.game_date) filter (
            where not schedule_season_games.is_completed
                and schedule_season_games.game_date >= as_of.as_of_date
        ) as next_game_date,
        max(schedule_season_games.game_date) filter (
            where schedule_season_games.is_completed
        ) as last_completed_game_date
    from seasons
    cross join as_of
    cross join schedule_season_games
    group by 1, 2

),

phased as (

    select
        *,
        -- The season the site is waiting on, which is not always one the feed
        -- carries. In the preseason it is the schedule that has arrived; in the
        -- offseason no row for it exists yet, so it is the one after the last
        -- season played. A page naming it in the offseason would otherwise name
        -- the season that just finished.
        case
            when upcoming_games = 0 then data_season + 1
            else schedule_season
        end as awaited_season

    from counts

),

final as (

    select
        'current' as season_status_id,
        schedule_season,
        data_season,
        awaited_season,
        -- 2027 reads as 2026-27, the way every source and every reader writes it.
        cast(schedule_season - 1 as varchar) || '-'
            || right(cast(schedule_season as varchar), 2) as schedule_season_label,
        cast(data_season - 1 as varchar) || '-'
            || right(cast(data_season as varchar), 2) as data_season_label,
        cast(awaited_season - 1 as varchar) || '-'
            || right(cast(awaited_season as varchar), 2) as awaited_season_label,
        schedule_season > data_season as is_preseason,
        upcoming_games = 0 as is_offseason,

        -- The single column a page switches on. Ordered so the offseason wins:
        -- once a schedule for the next season lands, `is_preseason` and a
        -- non-zero `upcoming_games` arrive together and the phase moves on by
        -- itself, with nothing to edit and no date written down anywhere.
        case
            when upcoming_games = 0 then 'offseason'
            when schedule_season > data_season then 'preseason'
            else 'in_season'
        end as phase,

        completed_games,
        unplayed_games,
        upcoming_games,
        next_game_date,
        -- What the offseason banner dates itself from. Read from the data
        -- rather than the clock, for the same reason `mart_upcoming_games`
        -- dates itself from the last result: a warehouse that is a day behind
        -- should say what it knows.
        last_completed_game_date

    from phased

)

select * from final
