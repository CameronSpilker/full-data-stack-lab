---
title: March Madness
---

<script>
    import ViewNav from '$lib/ViewNav.svelte';
</script>

<ViewNav current="march-madness" />

The NCAA tournament, simulated. A projected 64-team field (conference champions
plus the best at-large teams, seeded across four regions) is played out
<Value data={sims} column=simulations fmt='#,##0' /> times, and the odds below
are how often each result happened.

```sql sims
select
    max(simulations) as simulations,
    max(season) as season,
    (max(season) - 1)::varchar || '-' || right(max(season)::varchar, 2) as season_label
from tournament_odds
```

```sql season_status
select phase, schedule_season, schedule_season_label from season_status
```

{#if sims[0].season < season_status[0].schedule_season}

<Alert status="info">
Showing the final <Value data={sims} column=season_label /> simulation. The
<Value data={season_status} column=schedule_season_label /> run starts on the
first nightly run after that season has ratings, then reruns every morning
(twice a day in March).
</Alert>

{:else if season_status[0].phase === 'offseason'}

<Alert status="info">
Showing the final <Value data={sims} column=season_label /> simulation. The next
season's run starts once it tips off and has ratings.
</Alert>

{:else}

<Alert status="info">
<Value data={sims} column=season_label /> projected field, rerun every morning
(twice a day in March). It is a forecast of the bracket until Selection Sunday.
</Alert>

{/if}

```sql favourites
select
    odds.team_name,
    '/teams/' || odds.team_id as team_link,
    -- The team's own colours, for its bar: a list of teams where the colour
    -- says nothing but which team.
    team.team_color,
    team.team_secondary_color,
    odds.seed,
    odds.region_name,
    odds.conference_name,
    odds.record,
    odds.won_championship,
    odds.reached_final_four,
    odds.reached_elite_eight,
    odds.reached_sweet_16,
    odds.expected_wins
from tournament_odds as odds
left join team_season as team
    on odds.team_id = team.team_id and odds.season = team.season
order by odds.won_championship desc
limit 16
```

## Title contenders

<LogoBarChart
    data={favourites}
    colorColumn=team_color
    altColorColumn=team_secondary_color
    x=team_name
    y=won_championship
    swapXY=true
    title="Probability of winning the national championship"
    yFmt='pct1'
    sort=false
/>

## Every team in the field

Expected wins is the sum of a team's odds of winning each round. Each row opens
that team's page.

```sql field
select
    seed,
    team_name,
    '/teams/' || team_id as team_link,
    region_name,
    conference_name,
    record,
    bid_type,
    reached_sweet_16,
    reached_final_four,
    won_championship,
    expected_wins
from tournament_odds
order by expected_wins desc
```

<DataTable data={field} search=true rows=15 link=team_link>
    <Column id=seed title="Seed" />
    <Column id=team_name title="Team" />
    <Column id=region_name title="Region" />
    <Column id=conference_name title="Conference" />
    <Column id=record title="Record" />
    <Column id=bid_type title="Bid" />
    <Column id=reached_sweet_16 title="Sweet 16" fmt='pct0' contentType=colorscale />
    <Column id=reached_final_four title="Final Four" fmt='pct0' contentType=colorscale />
    <Column id=won_championship title="Title" fmt='pct1' contentType=colorscale />
    <Column id=expected_wins title="Exp. wins" fmt='0.00' />
</DataTable>

## Does seeding hold up?

Odds should fall as the seed number rises. Where they do not, the seeding and
the ratings disagree.

```sql by_seed
select
    seed,
    avg(won_championship) as title_odds,
    avg(reached_final_four) as final_four_odds,
    avg(reached_sweet_16) as sweet_16_odds,
    avg(expected_wins) as expected_wins
from tournament_odds
group by seed
order by seed
```

<LineChart
    data={by_seed}
    x=seed
    y={["sweet_16_odds", "final_four_odds", "title_odds"]}
    title="Advancement odds by seed line"
    yFmt='pct0'
    xAxisTitle="Seed"
/>

## The regions

```sql regions
select
    region_name,
    seed,
    team_name,
    conference_name,
    won_championship,
    expected_wins
from tournament_odds
order by region_name, seed
```

<DataTable data={regions} groupBy=region_name groupType=section rows=16>
    <Column id=seed title="Seed" />
    <Column id=team_name title="Team" />
    <Column id=conference_name title="Conference" />
    <Column id=expected_wins title="Exp. wins" fmt='0.00' contentType=colorscale />
    <Column id=won_championship title="Title" fmt='pct1' />
</DataTable>
