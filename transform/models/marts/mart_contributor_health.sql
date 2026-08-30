-- Community health signals per tool: how the contributor base is moving and
-- how heavy the open issue load is relative to project size.

with growth as (

    select * from {{ ref('mart_ecosystem_growth') }}

),

cadence as (

    select * from {{ ref('mart_release_cadence') }}

),

latest as (

    select
        tool_name,
        max_by(week_start, week_start) as as_of_week,
        max_by(contributor_count, week_start) as contributor_count,
        max_by(is_contributor_count_capped, week_start) as is_contributor_count_capped,
        max_by(stars, week_start) as stars,
        max_by(open_issues, week_start) as open_issues

    from growth
    group by 1

),

trend as (

    select
        tool_name,
        sum(contributors_added) as contributors_added_observed,
        count(*) filter (where contributors_added > 0) as weeks_with_new_contributors,
        count(*) as weeks_observed

    from growth
    group by 1

)

select
    latest.tool_name as contributor_health_id,
    latest.tool_name,
    cadence.category,
    latest.as_of_week,

    latest.contributor_count,
    latest.is_contributor_count_capped,
    trend.contributors_added_observed,
    trend.weeks_with_new_contributors,
    trend.weeks_observed,

    case
        when trend.weeks_observed > 0
            then trend.weeks_with_new_contributors * 1.0 / trend.weeks_observed
    end as share_of_weeks_growing,

    latest.open_issues,
    latest.stars,

    case
        when latest.stars > 0 then latest.open_issues * 1.0 / latest.stars
    end as open_issues_per_star,

    cadence.releases_last_90_days,
    cadence.days_since_latest_release

from latest

inner join trend
    on latest.tool_name = trend.tool_name

left join cadence
    on latest.tool_name = cadence.tool_name
