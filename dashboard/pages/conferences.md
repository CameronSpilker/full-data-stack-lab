---
title: Conferences
---

<script>
    import ViewNav from '$lib/ViewNav.svelte';
</script>

<ViewNav current="conferences" />

Leagues ranked on their **median** team, because depth predicts March better
than one great program does.

```sql seasons
select
    season,
    (season - 1)::varchar || '-' || right(season::varchar, 2) as season_label
from conference_strength
-- Only seasons with ratings: without them the ranks and charts are empty.
where median_efficiency_margin is not null
group by season
order by season desc
```

```sql season_pick
select coalesce(
    try_cast(nullif('${inputs.season.value}', '') as integer),
    (select max(season) from conference_strength where median_efficiency_margin is not null)
) as season
```

<Dropdown
    data={seasons}
    name=season
    value=season
    label=season_label
    title="Season"
    defaultValue={seasons[0]?.season}
/>

```sql conferences
select
    conference_rank,
    conference_name,
    team_count,
    median_efficiency_margin,
    best_efficiency_margin,
    best_team,
    teams_in_top_50,
    ncaa_bids
from conference_strength
where season = (select season from ${season_pick})
order by conference_rank
```

<DataTable data={conferences} rows=15 search=true>
    <Column id=conference_rank title="#" />
    <Column id=conference_name title="Conference" />
    <Column id=team_count title="Teams" />
    <Column id=median_efficiency_margin title="Median eff." fmt='+0.0;-0.0' contentType=colorscale />
    <Column id=best_efficiency_margin title="Best eff." fmt='+0.0;-0.0' />
    <Column id=best_team title="Best team" />
    <Column id=teams_in_top_50 title="Top 50" />
    <Column id=ncaa_bids title="Bids" />
</DataTable>

## Depth against peak

Right is a deeper league, up is a better top team. Bubble size is NCAA bids.

```sql depth
select
    conference_name,
    median_efficiency_margin,
    best_efficiency_margin,
    ncaa_bids
from conference_strength
where season = (select season from ${season_pick})
```

<ScatterPlot
    data={depth}
    x=median_efficiency_margin
    y=best_efficiency_margin
    size=ncaa_bids
    xAxisTitle="Median team's efficiency margin"
    yAxisTitle="Best team's efficiency margin"
    tooltipTitle=conference_name
/>

## Across seasons

```sql conference_list
select conference_name
from conference_strength
where season = (select season from ${season_pick})
order by conference_rank
```

<Dropdown
    data={conference_list}
    name=compare
    value=conference_name
    title="Conferences"
    multiple=true
    defaultValue={conference_list.slice(0, 3).map((d) => d.conference_name)}
/>

```sql over_time
-- The picked conferences, or the top three when nothing is picked. The pick is
-- read out of a dollar-quoted string rather than spliced in as a list, so the
-- same SQL runs whether the input holds a selection, an empty one, or nothing
-- yet while the page prerenders.
with picked as (
    select unnest(regexp_extract_all($$${inputs.compare.value}$$, '''([^'']+)''', 1)) as conference_name
),

shown as (
    select conference_name from picked
    union all
    select conference_name from (
        select conference_name
        from conference_strength
        where season = (select season from ${season_pick})
        order by conference_rank
        limit 3
    )
    where not exists (select 1 from picked)
)

select
    season,
    conference_name,
    median_efficiency_margin
from conference_strength
where conference_name in (select conference_name from shown)
order by season
```

<LineChart
    data={over_time}
    x=season
    y=median_efficiency_margin
    series=conference_name
    xFmt='0000'
    yFmt='+0.0'
    title="Median team rating by season"
/>
