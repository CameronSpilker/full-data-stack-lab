with source as (

    select * from {{ source('raw', 'github_repos') }}

),

renamed as (

    select
        {{ dbt_utils.generate_surrogate_key(['tool_name', 'snapshot_date']) }} as repo_snapshot_id,
        tool_name,
        repo_full_name,
        cast(snapshot_date as date) as snapshot_date,
        stars,
        forks,
        open_issues,
        watchers,
        size_kb,
        primary_language,
        license as license_id,
        cast(created_at as timestamp) as repo_created_at,
        cast(pushed_at as timestamp) as last_pushed_at,
        cast(extracted_at as timestamp) as extracted_at

    from source

)

select * from renamed
