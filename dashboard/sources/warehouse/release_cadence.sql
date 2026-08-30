select
    tool_name,
    repo_full_name,
    category,
    release_count,
    stable_release_count,
    releases_last_90_days,
    first_release_date,
    latest_release_date,
    avg_days_between_releases,
    median_days_between_releases,
    days_since_latest_release
from marts.mart_release_cadence
