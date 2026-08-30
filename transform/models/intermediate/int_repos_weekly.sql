-- Weekly repo metrics with the week-over-week deltas every mart needs.
-- Snapshots are taken on a weekly cadence; if a week is captured more than
-- once, the last snapshot in the week wins.

with repos as (

    select * from {{ ref('stg_github__repos') }}

),

contributors as (

    select * from {{ ref('stg_github__contributors') }}

),

registry as (

    select * from {{ ref('tool_registry') }}

),

weekly as (

    select
        repos.tool_name,
        date_trunc('week', repos.snapshot_date) as week_start,
        max(repos.snapshot_date) as snapshot_date,
        max_by(repos.stars, repos.snapshot_date) as stars,
        max_by(repos.forks, repos.snapshot_date) as forks,
        max_by(repos.open_issues, repos.snapshot_date) as open_issues,
        max_by(repos.watchers, repos.snapshot_date) as watchers,
        max_by(repos.primary_language, repos.snapshot_date) as primary_language,
        max_by(repos.license_id, repos.snapshot_date) as license_id,
        max_by(repos.repo_created_at, repos.snapshot_date) as repo_created_at,
        max_by(repos.last_pushed_at, repos.snapshot_date) as last_pushed_at

    from repos
    group by 1, 2

),

weekly_contributors as (

    select
        tool_name,
        date_trunc('week', snapshot_date) as week_start,
        max_by(contributor_count, snapshot_date) as contributor_count,
        max_by(is_count_capped, snapshot_date) as is_contributor_count_capped

    from contributors
    group by 1, 2

),

joined as (

    select
        {{ dbt_utils.generate_surrogate_key(['weekly.tool_name', 'weekly.week_start']) }}
            as repo_week_id,
        weekly.tool_name,
        registry.repo_full_name,
        registry.category,
        weekly.week_start,
        weekly.snapshot_date,
        weekly.stars,
        weekly.forks,
        weekly.open_issues,
        weekly.watchers,
        weekly.primary_language,
        weekly.license_id,
        weekly.repo_created_at,
        weekly.last_pushed_at,
        weekly_contributors.contributor_count,
        coalesce(weekly_contributors.is_contributor_count_capped, false)
            as is_contributor_count_capped,

        lag(weekly.stars) over tool_weeks as prior_week_stars,
        lag(weekly.forks) over tool_weeks as prior_week_forks,
        lag(weekly_contributors.contributor_count) over tool_weeks as prior_week_contributors

    from weekly

    left join weekly_contributors
        on weekly.tool_name = weekly_contributors.tool_name
        and weekly.week_start = weekly_contributors.week_start

    inner join registry
        on weekly.tool_name = registry.tool_name

    window tool_weeks as (partition by weekly.tool_name order by weekly.week_start)

),

final as (

    select
        *,
        stars - prior_week_stars as stars_added,
        forks - prior_week_forks as forks_added,
        contributor_count - prior_week_contributors as contributors_added,

        case
            when prior_week_stars > 0
                then (stars - prior_week_stars) * 1.0 / prior_week_stars
        end as star_growth_rate

    from joined

)

select * from final
