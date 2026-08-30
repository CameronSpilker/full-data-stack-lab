with source as (

    select * from {{ source('raw', 'github_releases') }}

),

-- Releases are re-extracted in full on every run, so keep only the most
-- recent observation of each tag.
deduplicated as (

    select
        *,
        row_number() over (
            partition by tool_name, release_tag
            order by snapshot_date desc
        ) as _recency

    from source

),

renamed as (

    select
        {{ dbt_utils.generate_surrogate_key(['tool_name', 'release_tag']) }} as release_id,
        tool_name,
        repo_full_name,
        release_tag,
        release_name,
        is_prerelease,
        cast(published_at as timestamp) as published_at,
        cast(published_at as date) as published_date,
        cast(extracted_at as timestamp) as extracted_at

    from deduplicated
    where _recency = 1
      and published_at is not null

)

select * from renamed
