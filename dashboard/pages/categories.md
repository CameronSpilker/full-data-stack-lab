---
title: Head to head
---

Every tool ranked inside its own category, as of the latest complete week.

```sql categories
select distinct category from tool_comparison order by category
```

<Dropdown data={categories} name=selected_category value=category title="Category">
    <DropdownOption value="orchestration" />
</Dropdown>

```sql category_standings
select
    tool_name,
    category,
    stars,
    forks,
    contributor_count,
    weekly_downloads,
    avg_star_growth_rate,
    category_rank_by_stars,
    category_rank_by_growth
from tool_comparison
where category = '${inputs.selected_category.value}'
order by category_rank_by_stars
```

<BarChart data={category_standings} x=tool_name y=stars title="Stars" swapXY=true />

<BarChart data={category_standings} x=tool_name y=avg_star_growth_rate title="Mean weekly star growth rate" swapXY=true />

<DataTable data={category_standings}>
    <Column id=tool_name title="Tool" />
    <Column id=category_rank_by_stars title="Rank by stars" />
    <Column id=category_rank_by_growth title="Rank by growth" />
    <Column id=stars title="Stars" fmt='#,##0' />
    <Column id=contributor_count title="Contributors" fmt='#,##0' />
    <Column id=weekly_downloads title="Weekly downloads" fmt='#,##0' />
</DataTable>
