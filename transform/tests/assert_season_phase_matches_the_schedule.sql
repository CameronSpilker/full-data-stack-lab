-- The one row every page switches on has to agree with itself.
--
-- `mart_season_status` is read by every page to decide whether to draw a chart
-- or a placeholder in its slot. That makes a wrong phase worse than a wrong
-- number: a page that believes the season is under way draws empty charts, and
-- a page that believes it is over hides live ones. Neither shows an error, so
-- nothing else would catch it.
--
-- The invariants, each of which is a way the phase could go wrong:
--
--   * `offseason` means nothing is left to play, and therefore no next game.
--   * `preseason` means the schedule has reached a season with no results in
--     it, and therefore there is something ahead to play. A preseason with
--     nothing upcoming is the offseason.
--   * `in_season` means both: results behind, fixtures ahead.
--   * Upcoming fixtures are a subset of unplayed ones, because the ones left
--     out are the games that were abandoned rather than played.
--   * The flags and the phase are two readings of the same thing, so they can
--     never disagree.

with status as (

    select * from {{ ref('mart_season_status') }}

),

violations as (

    select
        phase,
        is_preseason,
        is_offseason,
        completed_games,
        unplayed_games,
        upcoming_games,
        next_game_date,
        case
            when phase = 'offseason'
                and (upcoming_games <> 0 or next_game_date is not null)
                then 'offseason with a fixture still ahead'
            when phase = 'preseason'
                and (completed_games <> 0 or upcoming_games = 0)
                then 'preseason with results behind it, or nothing ahead of it'
            when phase = 'in_season'
                and (completed_games = 0 or upcoming_games = 0)
                then 'in season without both results behind and fixtures ahead'
            when upcoming_games > unplayed_games
                then 'more games upcoming than unplayed'
            when is_offseason <> (phase = 'offseason')
                then 'is_offseason disagrees with phase'
            when is_preseason <> (phase = 'preseason')
                then 'is_preseason disagrees with phase'
        end as problem

    from status

)

select * from violations
where problem is not null
