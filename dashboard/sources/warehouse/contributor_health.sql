select
    tool_name,
    category,
    as_of_week,
    contributor_count,
    is_contributor_count_capped,
    contributors_added_observed,
    weeks_with_new_contributors,
    weeks_observed,
    share_of_weeks_growing,
    open_issues,
    stars,
    open_issues_per_star,
    releases_last_90_days,
    days_since_latest_release
from marts.mart_contributor_health
