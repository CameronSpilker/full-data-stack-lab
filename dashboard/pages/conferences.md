---
title: Conferences
---

A conference is usually judged by its best team. That is the wrong measure — one
outstanding program can carry a league's reputation while the median team is mediocre.
Depth is what actually predicts March, so these are ranked on the **median** team's
rating rather than the mean or the maximum.

```sql season_status
select
    schedule_season_label,
    data_season_label,
    is_preseason,
    scheduled_games,
    next_game_date
from season_status
```

{#if season_status[0].is_preseason}

<Alert status="warning">

**The <Value data={season_status} column=schedule_season_label /> season has not
tipped off.** These standings describe <Value data={season_status} column=data_season_label />, the
last completed season, because a team that has not played a game cannot be rated,
ranked or seeded. <Value data={season_status} column=scheduled_games fmt='#,##0' />
games are on the schedule, the first of them
<Value data={season_status} column=next_game_date fmt='mmmm d' />.

The [upcoming picks](/picks) page is the one that has already moved on: a forecast
does not need results, so it is pricing those fixtures now.

</Alert>

{/if}

```sql conferences
select
    conference_rank,
    conference_name,
    team_count,
    median_efficiency_margin,
    avg_efficiency_margin,
    best_efficiency_margin,
    best_team,
    teams_in_top_25,
    teams_in_top_50,
    ncaa_bids,
    ncaa_tournament_wins,
    avg_tempo
from conference_strength
where season = (select max(season) from conference_strength)
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

The horizontal axis is the median team, the vertical axis the best one. A conference high
and to the right is strong throughout; high and to the left is one great team and not
much else.

```sql depth
select
    conference_name,
    median_efficiency_margin,
    best_efficiency_margin,
    team_count,
    ncaa_bids
from conference_strength
where season = (select max(season) from conference_strength)
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

## How leagues have moved

```sql over_time
select
    season,
    conference_name,
    median_efficiency_margin,
    conference_rank
from conference_strength
where conference_name in (
    select conference_name from conference_strength
    where season = (select max(season) from conference_strength)
    order by conference_rank
    limit 8
)
order by season
```

<LineChart
    data={over_time}
    x=season
    y=median_efficiency_margin
    series=conference_name
    title="Median team rating, top eight conferences"
/>
