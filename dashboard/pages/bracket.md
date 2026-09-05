---
title: Tournament Odds
---

```sql sims
select max(simulations) as simulations, max(season) as season from tournament_odds
```

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
tipped off.** This field and these odds describe <Value data={season_status} column=data_season_label />, the
last completed season, because a team that has not played a game cannot be rated,
ranked or seeded. <Value data={season_status} column=scheduled_games fmt='#,##0' />
games are on the schedule, the first of them
<Value data={season_status} column=next_game_date fmt='mmmm d' />.

The [upcoming picks](/picks) page is the one that has already moved on: a forecast
does not need results, so it is pricing those fixtures now.

</Alert>

{/if}

The bracket played <Value data={sims} column=simulations fmt='#,##0' /> times. Each
simulation plays all 63 games, drawing every result from the same matchup
probabilities the rest of the site uses, and the odds below are simply how often
each outcome happened.

<Alert status="info">

Before Selection Sunday there is no official bracket, so this field is
<strong>projected</strong>: automatic bids to conference tournament champions, at-large
places to the best remaining teams, seeded across four regions. It is a forecast of the
bracket, not the bracket.

</Alert>

```sql favourites
select
    team_name,
    '/teams/' || team_id as team_link,
    seed,
    region_name,
    conference_name,
    record,
    won_championship,
    reached_final_four,
    reached_elite_eight,
    reached_sweet_16,
    expected_wins
from tournament_odds
order by won_championship desc
limit 16
```

## Title contenders

<BarChart
    data={favourites}
    x=team_name
    y=won_championship
    swapXY=true
    title="Probability of winning the national championship"
    yFmt='pct1'
    sort=false
/>

## Every team in the field

`Expected wins` is the sum of a team's odds of surviving each round. It ranks a field
better than title odds do, because title odds are dominated by a handful of teams while
most of a bracket is decided by whether a 6 seed reaches the second weekend.

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

If the seeding is sound, title odds should fall steadily as the seed number rises. Where
it does not, the committee's ordering and the ratings disagree — which is exactly where
the value in a bracket pool is.

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
