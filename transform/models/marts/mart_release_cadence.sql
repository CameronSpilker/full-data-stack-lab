-- How actively each tool ships. One row per tool.

with releases as (

    select * from {{ ref('stg_github__releases') }}

),

registry as (

    select * from {{ ref('tool_registry') }}

),

gaps as (

    select
        tool_name,
        published_date,
        is_prerelease,
        date_diff(
            'day',
            lag(published_date) over (partition by tool_name order by published_date),
            published_date
        ) as days_since_prior_release

    from releases

),

aggregated as (

    select
        tool_name,
        count(*) as release_count,
        count(*) filter (where not is_prerelease) as stable_release_count,
        count(*) filter (where published_date >= current_date - interval 90 day)
            as releases_last_90_days,
        min(published_date) as first_release_date,
        max(published_date) as latest_release_date,
        avg(days_since_prior_release) as avg_days_between_releases,
        median(days_since_prior_release) as median_days_between_releases

    from gaps
    group by 1

)

select
    registry.tool_name as release_cadence_id,
    registry.tool_name,
    registry.repo_full_name,
    registry.category,

    coalesce(aggregated.release_count, 0) as release_count,
    coalesce(aggregated.stable_release_count, 0) as stable_release_count,
    coalesce(aggregated.releases_last_90_days, 0) as releases_last_90_days,
    aggregated.first_release_date,
    aggregated.latest_release_date,
    aggregated.avg_days_between_releases,
    aggregated.median_days_between_releases,

    date_diff('day', aggregated.latest_release_date, current_date)
        as days_since_latest_release

from registry

left join aggregated
    on registry.tool_name = aggregated.tool_name
