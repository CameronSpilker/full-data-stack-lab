-- The team dimension, reduced to the most recent snapshot.
--
-- Conference membership changes between seasons but the extractor only ever
-- holds current state, so the latest snapshot is the only defensible answer to
-- "what conference is this team in".
--
-- Columns the extractor has gained are read only when the stored table
-- actually has them. That is not defensive habit, it is the shape of this one
-- table: the daily run is `ingest daily`, which deliberately skips the team
-- dimension because it changes once a year, and the pipeline carries the
-- previous warehouse forward. So a new field here reaches dbt weeks before
-- anything re-extracts the teams, and a plain reference to it fails every
-- nightly run until a backfill happens to fill the gap. That is exactly what
-- `logo_url` did: the loader was taught to widen the stored table, but the
-- only run that widens it is the one this path never takes.
--
-- Nullable in both branches, so nothing downstream can tell the difference
-- between "not extracted yet" and "this team has none".
{% set stored = adapter.get_relation(
    database=source('raw', 'ncaa_teams').database,
    schema=source('raw', 'ncaa_teams').schema,
    identifier=source('raw', 'ncaa_teams').identifier
) %}
{% set stored_columns = [] %}
{% if execute and stored is not none %}
    {% set stored_columns = adapter.get_columns_in_relation(stored)
        | map(attribute='name') | map('lower') | list %}
{% endif %}

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
        {% if 'logo_url' in stored_columns -%}
        logo_url as team_logo_url,
        {%- else -%}
        cast(null as varchar) as team_logo_url,
        {%- endif %}
        is_active,
        {{ normalize_team_name('location') }} as team_match_key,
        cast(snapshot_date as date) as snapshot_date,
        cast(extracted_at as timestamp) as extracted_at

    from latest

)

select * from renamed
