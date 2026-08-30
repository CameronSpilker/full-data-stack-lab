select
    tool_name,
    repo_full_name,
    category,
    week_start,
    stars,
    stars_added,
    star_growth_rate,
    forks,
    open_issues,
    contributor_count,
    package_name,
    weekly_downloads,
    download_momentum,
    is_partial_download_week
from marts.mart_ecosystem_growth
