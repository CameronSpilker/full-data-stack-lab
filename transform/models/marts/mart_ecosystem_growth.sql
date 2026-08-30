-- One row per tool per week: the growth series the Overview and Tool Deep
-- Dive dashboard pages read.

with repos as (

    select * from {{ ref('int_repos_weekly') }}

),

packages as (

    select * from {{ ref('int_packages_weekly') }}

)

select
    repos.repo_week_id as ecosystem_growth_id,
    repos.tool_name,
    repos.repo_full_name,
    repos.category,
    repos.week_start,

    repos.stars,
    repos.stars_added,
    repos.star_growth_rate,
    repos.forks,
    repos.forks_added,
    repos.open_issues,
    repos.contributor_count,
    repos.contributors_added,
    repos.is_contributor_count_capped,

    packages.package_name,
    packages.downloads as weekly_downloads,
    packages.downloads_added as weekly_downloads_added,
    packages.download_momentum,
    coalesce(packages.is_partial_week, false) as is_partial_download_week

from repos

left join packages
    on repos.tool_name = packages.tool_name
    and repos.week_start = packages.week_start
