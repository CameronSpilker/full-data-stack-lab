-- Weekly PyPI downloads joined to the repo metrics for the same tool and week.
-- Partial weeks at the edges of the pypistats window are flagged rather than
-- dropped, so a chart can exclude them without losing the row.

with downloads as (

    select * from {{ ref('stg_pypi__downloads') }}

),

repos_weekly as (

    select * from {{ ref('int_repos_weekly') }}

),

registry as (

    select * from {{ ref('tool_registry') }}

),

weekly as (

    select
        tool_name,
        package_name,
        date_trunc('week', download_date) as week_start,
        sum(downloads) as downloads,
        count(*) as days_observed,
        min(download_date) as first_day,
        max(download_date) as last_day

    from downloads
    group by 1, 2, 3

),

with_deltas as (

    select
        {{ dbt_utils.generate_surrogate_key(['tool_name', 'week_start']) }} as package_week_id,
        *,
        days_observed < 7 as is_partial_week,
        lag(downloads) over (partition by package_name order by week_start)
            as prior_week_downloads

    from weekly

),

final as (

    select
        with_deltas.package_week_id,
        with_deltas.tool_name,
        with_deltas.package_name,
        registry.category,
        with_deltas.week_start,
        with_deltas.downloads,
        with_deltas.days_observed,
        with_deltas.is_partial_week,
        with_deltas.prior_week_downloads,
        with_deltas.downloads - with_deltas.prior_week_downloads as downloads_added,

        case
            when with_deltas.prior_week_downloads > 0
                then (with_deltas.downloads - with_deltas.prior_week_downloads)
                     * 1.0 / with_deltas.prior_week_downloads
        end as download_momentum,

        repos_weekly.stars,
        repos_weekly.contributor_count

    from with_deltas

    inner join registry
        on with_deltas.tool_name = registry.tool_name

    left join repos_weekly
        on with_deltas.tool_name = repos_weekly.tool_name
        and with_deltas.week_start = repos_weekly.week_start

)

select * from final
