with source as (

    select * from {{ source('raw', 'github_contributors') }}

),

renamed as (

    select
        {{ dbt_utils.generate_surrogate_key(['tool_name', 'snapshot_date']) }}
            as contributor_snapshot_id,
        tool_name,
        repo_full_name,
        cast(snapshot_date as date) as snapshot_date,
        contributor_count,

        -- GitHub caps the paginated contributor list at 500 for large repos,
        -- so anything at the ceiling is a floor, not an exact count.
        contributor_count >= 500 as is_count_capped,

        cast(extracted_at as timestamp) as extracted_at

    from source

)

select * from renamed
