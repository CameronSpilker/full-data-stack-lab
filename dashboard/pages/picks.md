---
title: Upcoming picks
---

<script>
    import ViewNav from '$lib/ViewNav.svelte';
    import AwaitingData from '$lib/AwaitingData.svelte';
</script>

<ViewNav current="picks" />

What the model makes of games not played yet, rebuilt every morning. Read the
**edge** column: where the model and the betting market disagree. The market is
usually right ([model accuracy](/model)).

```sql season_status
select
    schedule_season_label,
    data_season_label,
    awaited_season_label,
    phase,
    upcoming_games,
    next_game_date,
    last_completed_game_date
from season_status
```

{#if season_status[0].phase === 'offseason'}

<Alert status="info">

No fixtures to price until the <Value data={season_status} column=awaited_season_label />
schedule lands. The tables come back on the first nightly run after it does.

</Alert>

{/if}

```sql slate
select
    max(as_of_date) as as_of_date,
    count(*) filter (where days_out <= 7) as games_this_week,
    count(*) filter (where days_out <= 7 and edge_vs_market is not null) as priced,
    count(*) filter (
        where days_out <= 7 and forecast_basis <> 'current_season'
    ) as on_last_season,
    count(*) as games_scheduled
from upcoming_games
```

{#if slate[0].games_scheduled > 0}

<Grid cols=4>
    <BigValue data={slate} value=as_of_date title="Results through" fmt='mmm d' />
    <BigValue data={slate} value=games_this_week title="Games in the next 7 days" fmt='#,##0' />
    <BigValue data={slate} value=priced title="With a posted line" fmt='#,##0' />
    <BigValue data={slate} value=on_last_season title="Rated partly on last season" fmt='#,##0' />
</Grid>

In November many teams are still rated partly on last season (the last tile).
By January that tile reads zero.

{:else}

<AwaitingData
    title="The slate"
    detail="Counts for the next seven days. Fills in when the schedule does."
    height={140}
/>

{/if}

## Where the model disagrees with the price

The ten games this week where the model likes a side most above its price.

```sql edges
select
    game_date,
    pick_team_name,
    pick_opponent_name,
    '/teams/' || pick_team_id as team_link,
    case when pick_is_home then 'Home' else 'Away' end as venue,
    pick_win_probability,
    market_probability_for_pick,
    edge_vs_market,
    pick_moneyline,
    expected_value_per_dollar,
    is_market_underdog
from upcoming_games
where edge_rank <= 10
order by edge_rank
```

{#if edges.length > 0}

<DataTable data={edges} rows=10 link=team_link>
    <Column id=game_date title="Date" fmt='mmm d' />
    <Column id=pick_team_name title="Pick" />
    <Column id=pick_opponent_name title="Against" />
    <Column id=venue title="At" />
    <Column id=pick_win_probability title="Model" fmt='pct0' />
    <Column id=market_probability_for_pick title="Market" fmt='pct0' />
    <Column id=edge_vs_market title="Edge" fmt='+0.0%;-0.0%' contentType=colorscale />
    <Column id=pick_moneyline title="Price" fmt='+#,##0;-#,##0' />
    <Column id=expected_value_per_dollar title="Per $1" fmt='+0.00;-0.00' />
</DataTable>

{:else}

<AwaitingData
    title="The ten biggest disagreements with the price"
    detail="Needs games this week with a posted line."
    height={160}
/>

{/if}

## The upsets it likes

The same, limited to underdogs.

```sql upsets
select
    game_date,
    pick_team_name,
    pick_opponent_name,
    '/teams/' || pick_team_id as team_link,
    pick_win_probability,
    market_probability_for_pick,
    edge_vs_market,
    pick_moneyline,
    expected_value_per_dollar
from upcoming_games
where upset_rank <= 10
order by upset_rank
```

{#if upsets.length > 0}

<DataTable data={upsets} rows=10 link=team_link>
    <Column id=game_date title="Date" fmt='mmm d' />
    <Column id=pick_team_name title="Underdog" />
    <Column id=pick_opponent_name title="Against" />
    <Column id=pick_win_probability title="Model" fmt='pct0' />
    <Column id=market_probability_for_pick title="Market" fmt='pct0' />
    <Column id=edge_vs_market title="Edge" fmt='+0.0%;-0.0%' contentType=colorscale />
    <Column id=pick_moneyline title="Price" fmt='+#,##0;-#,##0' />
    <Column id=expected_value_per_dollar title="Per $1" fmt='+0.00;-0.00' />
</DataTable>

{:else}

<AwaitingData
    title="The upsets the model likes"
    detail="Needs games this week with a posted line."
    height={160}
/>

{/if}

## Model against market, every priced game this week

One point per game. The diagonal is agreement; above it the model likes the pick
more than the market does.

```sql agreement
select
    pick_team_name,
    pick_opponent_name,
    market_probability_for_pick,
    pick_win_probability,
    edge_vs_market,
    case when is_market_underdog then 'Model takes the dog' else 'Model takes the favourite' end
        as side
from upcoming_games
where days_out <= 7
    and edge_vs_market is not null
```

{#if agreement.length > 0}

<LogoScatter
    data={agreement}
    x=market_probability_for_pick
    y=pick_win_probability
    series=side
    seriesColors={{'Model takes the dog': 'viz-test', 'Model takes the favourite': 'viz-muted'}}
    xAxisTitle="What the market gives the pick"
    yAxisTitle="What the model gives the pick"
    xFmt='pct0'
    yFmt='pct0'
    chartAreaHeight=300
    tooltipTitle=pick_team_name
/>

{:else}

<AwaitingData
    title="Model against market, every priced game this week"
    detail="Needs games this week with a posted line."
    height={300}
/>

{/if}

## The ten it is most sure about

Ranked on confidence alone. "Has won" is how often past forecasts at that
confidence came in.

```sql confident
select
    game_date,
    pick_team_name,
    pick_opponent_name,
    '/teams/' || pick_team_id as team_link,
    pick_win_probability,
    pick_margin,
    pick_moneyline,
    historical_win_rate_at_confidence,
    historical_games_at_confidence
from upcoming_games
where confidence_rank <= 10
order by confidence_rank
```

{#if confident.length > 0}

<DataTable data={confident} rows=10 link=team_link>
    <Column id=game_date title="Date" fmt='mmm d' />
    <Column id=pick_team_name title="Pick" />
    <Column id=pick_opponent_name title="Against" />
    <Column id=pick_win_probability title="Model" fmt='pct0' />
    <Column id=pick_margin title="By" fmt='0.0' />
    <Column id=pick_moneyline title="Price" fmt='+#,##0;-#,##0' />
    <Column id=historical_win_rate_at_confidence title="Has won" fmt='pct0' />
    <Column id=historical_games_at_confidence title="In" fmt='#,##0' />
</DataTable>

{:else}

<AwaitingData
    title="The ten the model is most sure about"
    detail="Needs games in the next seven days."
    height={160}
/>

{/if}

## The whole slate

Every game in the next seven days, by date.

```sql week
select
    game_date,
    home_team_name,
    away_team_name,
    home_rank,
    away_rank,
    predicted_home_margin,
    home_win_probability,
    pick_team_name,
    pick_win_probability,
    consensus_home_spread,
    edge_vs_market,
    is_neutral_site
from upcoming_games
where days_out <= 7
order by game_date, pick_win_probability desc
```

{#if week.length > 0}

<DataTable data={week} rows=15 search=true>
    <Column id=game_date title="Date" fmt='mmm d' />
    <Column id=home_team_name title="Home" />
    <Column id=away_team_name title="Away" />
    <Column id=predicted_home_margin title="Model line" fmt='+0.0;-0.0' />
    <Column id=consensus_home_spread title="Market line" fmt='+0.0;-0.0' />
    <Column id=pick_team_name title="Pick" />
    <Column id=pick_win_probability title="Model" fmt='pct0' />
    <Column id=edge_vs_market title="Edge" fmt='+0.0%;-0.0%' contentType=colorscale />
</DataTable>

{:else}

<AwaitingData
    title="Every scheduled game in the next week"
    detail="Fills in when the schedule does."
    height={200}
/>

{/if}

## How a pick is made

Both teams are rated on adjusted efficiency (60%) and Elo (40%), plus 3.5 points
for home court. The margin becomes a probability, and the market's median line
is converted the same way and subtracted to give the edge. Full detail is on
[how it works](/how-it-works).

Not betting advice.
