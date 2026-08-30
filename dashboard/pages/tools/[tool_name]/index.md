# {params.tool_name}

```sql tool_detail
select *
from ecosystem_growth
where tool_name = '${params.tool_name}'
order by week_start
```

```sql tool_latest
select *
from tool_comparison
where tool_name = '${params.tool_name}'
```

<BigValue data={tool_latest} value=stars title="Stars" fmt='#,##0' />
<BigValue data={tool_latest} value=forks title="Forks" fmt='#,##0' />
<BigValue data={tool_latest} value=contributor_count title="Contributors" fmt='#,##0' />
<BigValue data={tool_latest} value=weekly_downloads title="Weekly downloads" fmt='#,##0' />

## Stars

<LineChart data={tool_detail} x=week_start y=stars title="Stars over time" />

## Weekly stars added

<BarChart data={tool_detail} x=week_start y=stars_added title="Stars gained per week" />

## PyPI downloads

<LineChart data={tool_detail} x=week_start y=weekly_downloads title="Weekly downloads" />

## Release activity

```sql tool_releases
select *
from release_cadence
where tool_name = '${params.tool_name}'
```

<DataTable data={tool_releases}>
    <Column id=release_count title="Releases" />
    <Column id=releases_last_90_days title="Last 90 days" />
    <Column id=median_days_between_releases title="Median days between" fmt='#,##0.0' />
    <Column id=days_since_latest_release title="Days since latest" />
</DataTable>
