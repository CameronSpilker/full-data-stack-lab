---
title: Upcoming picks
---

Every other page here grades a prediction against a game that already
happened. This one does not: it is what the model makes of games nobody has
played yet, rebuilt every morning from last night's results.

That makes it the only page where the full model is honestly point-in-time. In
the [backtest](/model), the blended predictor has to be labelled as a model
that saw the future, because scoring a January game with a rating that
describes the whole season means using March information. A game that has not
been played has no future to leak.

**Read the edge column, not the probability column.** The model is very sure
about a lot of games, and so is everyone else: a 95% favourite is 95% on every
screen in the country and priced accordingly. The only interesting number here
is where the model and the betting market disagree, and even then the market
is the better forecaster more often than not. The
[accuracy page](/model) is where that claim gets checked.

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

<Grid cols=4>
    <BigValue data={slate} value=as_of_date title="Results through" fmt='mmm d' />
    <BigValue data={slate} value=games_this_week title="Games in the next 7 days" fmt='#,##0' />
    <BigValue data={slate} value=priced title="With a posted line" fmt='#,##0' />
    <BigValue data={slate} value=on_last_season title="Rated partly on last season" fmt='#,##0' />
</Grid>

The last tile is the one to watch in November. A team that has played fewer
than ten games is rated partly on what it carried out of last season, and a
matchup counts against that tile if either side is. Early in a season most of
the card is, the model is at its worst, and the edges it reports are mostly its
own error. By January the tile reads zero.

Dated from the last day a game was played rather than from the clock, so a
warehouse that is a day behind says what it knows instead of describing a
slate its data never reached.

{#if slate[0].games_scheduled === 0}

**There are no games left on the schedule.** Either the season has finished or
the next one has not been published yet, so every table below is empty. That is
the correct answer rather than a broken page: the forecast rebuilds itself the
morning the first fixture lands.

{/if}

## Where the model disagrees with the price

The ten games in the next week where the model's probability is furthest above
what the market is charging for the same side. Positive edge means the model
thinks the price is too long. This is the list to read first.

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

## The upsets it likes

The same disagreement, restricted to games where the model is taking the side
the market has priced as the underdog. These are the picks that lose most of
the time and pay for it when they do not, which is a different bet from the
one above and worth separating.

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

## Model against market, every priced game this week

Each point is one game, plotted at what the market gives the model's pick
against what the model gives it. The diagonal is agreement. Everything above
the line is a game the model likes more than the price does, and the further
from the line, the bigger the claim being made.

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

<ScatterPlot
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

## The ten it is most sure about

Sorted on the model's own confidence, with no reference to a price. Most of
these are unbettable at the number the market posts, which is exactly why the
edge tables above lead the page. The last column is the check on the number
beside it: across every season in the warehouse, this is how often a real
forecast at that confidence has actually won.

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

## The whole slate

Every scheduled game in the next week, whether or not a book has posted it.
Sorted by date, so this is the card rather than a ranking.

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

## How a pick is made

Same predictor as everywhere else on this site, defined once in a dbt macro so
the bracket, the head-to-head numbers and this page cannot disagree about the
same game.

1. **Rate both teams as of today.** Adjusted efficiency margin, tempo, and Elo.
   A team that has played fewer than ten games this season is rated partly on
   what it carried out of last season, regressed toward the league, because a
   rating built from four games is mostly noise and on opening night there is
   no rating at all.
2. **Turn the two ratings into an expected margin.** Efficiency at 60% weight
   and Elo at 40%, tempo-adjusted, plus 3.5 points to the home side and
   nothing at a neutral site.
3. **Turn the margin into a probability** with the logistic the betting
   market's own spread-to-moneyline conversion uses, so the model and the
   benchmark are on one scale.
4. **Compare it to the price.** Every book's spread and moneyline is reduced
   to a median, converted the same way, and subtracted. What is left is the
   edge column.
5. **Rank, and stop at seven days out.** Anything further ahead has no line to
   disagree with, so it sits in the slate table without a rank.

The ratings this runs on are the same ones the [season overview](/) ranks
teams with, and the accuracy of the predictor behind it is on the
[model page](/model), including how badly it is calibrated where it is badly
calibrated.

None of this is betting advice, and the numbers are only as good as that
calibration curve. A model that is overconfident at 80% will produce a
confident-looking edge on every game it is wrong about.
