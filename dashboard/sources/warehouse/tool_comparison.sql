select
    tool_name,
    repo_full_name,
    category,
    as_of_week,
    stars,
    forks,
    open_issues,
    contributor_count,
    package_name,
    weekly_downloads,
    avg_weekly_stars_added,
    avg_star_growth_rate,
    avg_weekly_downloads,
    category_rank_by_stars,
    category_rank_by_growth
from marts.mart_tool_comparison
