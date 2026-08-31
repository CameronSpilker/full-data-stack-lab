-- The team dimension, reduced to the most recent snapshot.
--
-- Conference membership changes between seasons but the extractor only ever
-- holds current state, so the latest snapshot is the only defensible answer to
-- "what conference is this team in".

with source as (

    select * from {{ source('raw', 'ncaa_teams') }}

),

latest as (

    select *
    from source
    qualify row_number() over (partition by team_id order by snapshot_date desc) = 1

),

renamed as (

    select
        cast(team_id as varchar) as team_id,
        location as team_location,
        mascot,
        display_name as team_name,
        coalesce(short_name, location) as team_short_name,
        abbreviation as team_abbreviation,
        team_slug,
        cast(conference_id as varchar) as conference_id,
        conference_name,
        venue_name,
        venue_city,
        venue_state,
        color as team_color,
        is_active,
        {{ normalize_team_name('location') }} as team_match_key,
        cast(snapshot_date as date) as snapshot_date,
        cast(extracted_at as timestamp) as extracted_at

    from latest

)

select * from renamed
