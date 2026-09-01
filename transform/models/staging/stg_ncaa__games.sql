-- One row per game, typed and classified.
--
-- `game_type` is derived here rather than in a mart because every downstream
-- consumer needs it and the parsing is source-specific: ESPN puts the round in
-- a free-text note whose wording has changed over the years, so this matches
-- on the part that has not.

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
        coalesce(is_completed, false) as is_completed,
        status_state,
        attendance,
        venue_name,
        tournament_note,
        cast(extracted_at as timestamp) as extracted_at

    from source

),

classified as (

    select
        *,

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

    from typed

)

select * from classified
