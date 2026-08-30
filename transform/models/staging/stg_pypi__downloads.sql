with source as (

    select * from {{ source('raw', 'pypi_downloads') }}

),

-- pypistats reports a trailing window on every run, so the same day is
-- re-extracted many times. Keep the latest observation of each day.
deduplicated as (

    select
        *,
        row_number() over (
            partition by package_name, download_date
            order by snapshot_date desc
        ) as _recency

    from source
    where category = 'without_mirrors'

),

renamed as (

    select
        {{ dbt_utils.generate_surrogate_key(['package_name', 'download_date']) }} as download_id,
        tool_name,
        package_name,
        cast(download_date as date) as download_date,
        downloads,
        cast(extracted_at as timestamp) as extracted_at

    from deduplicated
    where _recency = 1

)

select * from renamed
