---
title: Community health
---

Signals about the people behind each project: how often the contributor base
grows, how heavy the open issue load is relative to project size, and how
recently the project shipped.

<Alert status="info">

Contributor counts are read from GitHub's paginated contributor list, which
caps at 500 for large repos. Any tool at that ceiling is a floor, not an exact
count — the <code>is_contributor_count_capped</code> flag marks them.

</Alert>

```sql health
select
    tool_name,
    category,
    contributor_count,
    is_contributor_count_capped,
    share_of_weeks_growing,
    open_issues,
    open_issues_per_star,
    releases_last_90_days,
    days_since_latest_release
from contributor_health
order by contributor_count desc
```

<BarChart data={health} x=tool_name y=contributor_count title="Contributors" swapXY=true />

<ScatterPlot data={health} x=contributor_count y=releases_last_90_days series=category tooltipTitle=tool_name title="Contributors vs. releases in the last 90 days" />

<DataTable data={health} search=true rows=20>
    <Column id=tool_name title="Tool" />
    <Column id=category title="Category" />
    <Column id=contributor_count title="Contributors" fmt='#,##0' />
    <Column id=share_of_weeks_growing title="Weeks growing" fmt='0%' />
    <Column id=open_issues_per_star title="Open issues / star" fmt='0.000' />
    <Column id=releases_last_90_days title="Releases (90d)" />
    <Column id=days_since_latest_release title="Days since release" />
</DataTable>
