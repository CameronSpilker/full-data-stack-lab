-- Head-to-head standing within a category, as of the latest complete week.
-- Powers the Orchestrators / Warehouses / BI Tools dashboard pages.

with growth as (

    select * from {{ ref('mart_ecosystem_growth') }}

),

latest_week as (

    select max(week_start) as week_start from growth

),

current_standing as (

    select growth.*
    from growth
    inner join latest_week on growth.week_start = latest_week.week_start

),

-- A trailing average smooths the weekly noise a single snapshot shows.
trailing_averages as (

    select
        tool_name,
        avg(stars_added) as avg_weekly_stars_added,
        avg(star_growth_rate) as avg_star_growth_rate,
        avg(weekly_downloads) as avg_weekly_downloads

    from growth
    where stars_added is not null
    group by 1

)

select
    current_standing.tool_name as tool_comparison_id,
    current_standing.tool_name,
    current_standing.repo_full_name,
    current_standing.category,
    current_standing.week_start as as_of_week,

    current_standing.stars,
    current_standing.forks,
    current_standing.open_issues,
    current_standing.contributor_count,
    current_standing.package_name,
    current_standing.weekly_downloads,

    trailing_averages.avg_weekly_stars_added,
    trailing_averages.avg_star_growth_rate,
    trailing_averages.avg_weekly_downloads,

    row_number() over (
        partition by current_standing.category
        order by current_standing.stars desc
    ) as category_rank_by_stars,

    row_number() over (
        partition by current_standing.category
        order by trailing_averages.avg_star_growth_rate desc nulls last
    ) as category_rank_by_growth

from current_standing

left join trailing_averages
    on current_standing.tool_name = trailing_averages.tool_name
