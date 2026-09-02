-- One row per game, typed and classified.
--
-- `game_type` is derived here rather than in a mart because every downstream
-- consumer needs it and the parsing is source-specific: ESPN puts the round in
-- a free-text note whose wording has changed over the years, so this matches
-- on the part that has not.
--
-- `scoring_status` is the other thing that has to be settled once, here. The
-- source calls a row final whenever the game is off the schedule, which
-- includes fixtures nobody played: COVID forfeits carrying an administrative
-- 2-0, cancellations left at 0-0, and a handful of records where one side's
-- score was never filled in. Every one of those is a legitimate row about the
-- season and a poisonous row for a model that reads margins, so they are
-- labelled rather than deleted, and `is_completed` means "played", which is
-- the question every downstream model is actually asking.

with source as (

    select * from {{ source('raw', 'ncaa_games') }}

),

typed as (

    select
        cast(game_id as varchar) as game_id,
        cast(season as integer) as season,
        cast(season_type as integer) as season_type,
        cast(game_date as date) as game_date,
        cast(tipoff_at as timestamp) as tipoff_at,

        cast(home_team_id as varchar) as home_team_id,
        home_team_name,
        home_team_abbreviation,
        cast(home_conference_id as varchar) as home_conference_id,
        cast(home_score as integer) as home_score,
        cast(home_ap_rank as integer) as home_ap_rank,

        cast(away_team_id as varchar) as away_team_id,
        away_team_name,
        away_team_abbreviation,
        cast(away_conference_id as varchar) as away_conference_id,
        cast(away_score as integer) as away_score,
        cast(away_ap_rank as integer) as away_ap_rank,

        coalesce(is_neutral_site, false) as is_neutral_site,
        coalesce(is_conference_game, false) as is_conference_game,
        -- Kept as the source gave it. `scoring_status` below decides what it
        -- means, and the gap between the two is what the freshness tests watch.
        coalesce(is_completed, false) as source_says_completed,
        status_state,
        attendance,
        venue_name,
        tournament_note,
        cast(extracted_at as timestamp) as extracted_at

    from source

),

graded as (

    select
        *,

        case
            when not source_says_completed then 'scheduled'
            when home_score is null or away_score is null then 'unrecorded'
            -- A cancelled fixture the source still calls final.
            when home_score + away_score = 0 then 'not_played'
            -- An administrative result. The NCAA records a forfeit as 2-0 (or
            -- 1-0 for a no-contest), so the win is real and the scoreline is
            -- not: there is no margin, no pace, and no box score behind it.
            when least(home_score, away_score) = 0
                and greatest(home_score, away_score) <= 2 then 'forfeit'
            -- Everything else outside the band is a bad record. Three exist in
            -- the seasons this project loads, all of them a game where one
            -- side's score is missing digits.
            when least(home_score, away_score) < {{ var('plausible_score_min') }}
                or greatest(home_score, away_score) > {{ var('plausible_score_max') }}
                then 'implausible'
            else 'played'
        end as scoring_status

    from typed

),

classified as (

    select
        *,

        scoring_status = 'played' as is_completed,

        case
            when lower(coalesce(tournament_note, '')) like '%ncaa%' then 'ncaa_tournament'
            when lower(coalesce(tournament_note, '')) like '%conference tournament%'
                or lower(coalesce(tournament_note, '')) like '%conf tournament%'
                then 'conference_tournament'
            when tournament_note is not null then 'other_postseason'
            else 'regular_season'
        end as game_type,

        case
            when lower(coalesce(tournament_note, '')) not like '%ncaa%' then null
            when lower(tournament_note) like '%championship%'
                and lower(tournament_note) not like '%first%' then 'National Championship'
            when lower(tournament_note) like '%final four%' then 'Final Four'
            when lower(tournament_note) like '%elite eight%' then 'Elite Eight'
            when lower(tournament_note) like '%sweet 16%'
                or lower(tournament_note) like '%sweet sixteen%' then 'Sweet 16'
            when lower(tournament_note) like '%second round%' then 'Second Round'
            when lower(tournament_note) like '%first round%' then 'First Round'
            when lower(tournament_note) like '%first four%' then 'First Four'
        end as tournament_round,

        case
            when home_score > away_score then home_team_id
            when away_score > home_score then away_team_id
        end as winning_team_id,

        home_score - away_score as home_margin,
        home_score + away_score as total_points

    from graded

)

select * from classified
