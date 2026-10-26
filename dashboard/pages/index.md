---
title: NCAA Division I Men's Basketball
---

<script>
    import ViewNav from '$lib/ViewNav.svelte';
</script>

<ViewNav current="index" />

Every Division I men's team, season by season. Pick a season. Every number
comes from a tested dbt model ([how it works](/how-it-works)).

```sql seasons
-- Every season the warehouse has rated, newest first, labelled the way the
-- sport writes them: 2026 is the 2025-26 season.
select
    season,
    (season - 1)::varchar || '-' || right(season::varchar, 2) as season_label
from team_season
-- Only seasons with ratings: without them the ranks and charts are empty.
where adjusted_efficiency_margin is not null
group by season
order by season desc
```

```sql season_pick
-- Every query below reads its season from here. Before anyone touches the
-- dropdown, and while the page prerenders with no inputs, that is the latest.
select coalesce(
    try_cast(nullif('${inputs.season.value}', '') as integer),
    (select max(season) from team_season where adjusted_efficiency_margin is not null)
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

```sql season_status
select phase, schedule_season_label, data_season_label, next_game_date
from season_status
```

{#if season_status[0].phase === 'preseason'}

<Alert status="warning">
The <Value data={season_status} column=schedule_season_label /> season tips off
<Value data={season_status} column=next_game_date fmt='mmmm d' />. Until then the
latest season here is <Value data={season_status} column=data_season_label />.
</Alert>

{/if}

```sql totals
select
    count(*) as teams,
    count(distinct conference_name) as conferences
from team_season
where season = (select season from ${season_pick})
```

```sql games_played
select count(*) as games from game_results
where season = (select season from ${season_pick})
    and is_completed
```

<Grid cols=3>
    <BigValue data={totals} value=teams title="Division I teams" />
    <BigValue data={totals} value=conferences title="Conferences" />
    <BigValue data={games_played} value=games title="Games played" fmt='#,##0' />
</Grid>

## The top 25

Ranked on adjusted efficiency margin: points scored minus points allowed per 100
possessions, adjusted for opponent.

```sql top_teams
select
    national_rank,
    team_name,
    '/teams/' || team_id as team_link,
    conference_name,
    record,
    adjusted_efficiency_margin,
    adjusted_offensive_efficiency,
    adjusted_defensive_efficiency,
    adjusted_tempo,
    elo_rating
from team_season
where season = (select season from ${season_pick})
order by national_rank
limit 25
```

<DataTable data={top_teams} rows=12 link=team_link>
    <Column id=national_rank title="#" />
    <Column id=team_name title="Team" />
    <Column id=conference_name title="Conference" />
    <Column id=record title="Record" />
    <Column id=adjusted_efficiency_margin title="Net eff." fmt='+0.0;-0.0' contentType=colorscale />
    <Column id=adjusted_offensive_efficiency title="Off." fmt='0.0' />
    <Column id=adjusted_defensive_efficiency title="Def." fmt='0.0' />
    <Column id=adjusted_tempo title="Tempo" fmt='0.0' />
    <Column id=elo_rating title="Elo" fmt='#,##0' />
</DataTable>

## Offense against defense

Up and to the right is good at both ends.

```sql quadrant
select
    team_name,
    conference_name,
    adjusted_offensive_efficiency,
    adjusted_defensive_efficiency,
    case when national_rank <= 25 then 'Top 25' else 'Everyone else' end as tier,
    -- The top 25 are drawn last so they land on top of the cloud.
    case when national_rank <= 25 then 1 else 0 end as is_top
from team_season
where season = (select season from ${season_pick})
    and adjusted_offensive_efficiency is not null
order by is_top
```

<LogoScatter
    data={quadrant}
    x=adjusted_offensive_efficiency
    y=adjusted_defensive_efficiency
    series=tier
    seriesColors={{'Top 25': 'viz-model', 'Everyone else': 'viz-muted'}}
    xAxisTitle="Adjusted offense (points per 100)"
    yAxisTitle="Adjusted defense (points allowed per 100)"
    yInverted=true
    chartAreaHeight=300
    tooltipTitle=team_name
/>

## Biggest upsets

The results Elo thought least likely before tip-off.

```sql upsets
select
    game_date,
    case when home_margin > 0 then home_team_name else away_team_name end as winner,
    case when home_margin > 0 then away_team_name else home_team_name end as loser,
    abs(home_margin) as margin,
    case when home_margin > 0
        then elo_home_win_probability
        else 1 - elo_home_win_probability
    end as winner_pregame_probability
from game_results
where season = (select season from ${season_pick})
    and elo_home_win_probability is not null
order by winner_pregame_probability
limit 10
```

<DataTable data={upsets} rows=10>
    <Column id=game_date title="Date" fmt='mmm d, yyyy' />
    <Column id=winner title="Winner" />
    <Column id=loser title="Beat" />
    <Column id=margin title="By" />
    <Column id=winner_pregame_probability title="Pregame odds" fmt='pct1' contentType=colorscale colorScale=negative />
</DataTable>
