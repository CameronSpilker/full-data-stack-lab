---
title: How good is the model?
---

A predictor that never reports its own accuracy is a horoscope. This page is the
scoreboard for the one on this site.

## Read this first

```sql model_summary
select
    model_name,
    max(is_point_in_time) as is_point_in_time,
    sum(games_scored) as games,
    sum(accuracy * games_scored) / sum(games_scored) as accuracy,
    sum(log_loss * games_scored) / sum(games_scored) as log_loss,
    sum(brier_score * games_scored) / sum(games_scored) as brier_score,
    sum(mean_absolute_margin_error * games_scored) / sum(games_scored) as margin_error
from model_accuracy
group by model_name
order by log_loss
```

Three models are scored here, and **they are not all comparable**:

- **`elo_pregame`** — a genuine forecast. Its rating going into a game was built only
  from games already played, so nothing about the result leaked into the prediction.
- **`market_consensus`** — the betting market's closing line, converted to a
  probability. This is the benchmark, not a model of ours. Beating it is hard, and most
  models do not.
- **`blended_season_ratings`** — the full model, but scored against **end-of-season**
  efficiency ratings. Predicting a January game with a rating that describes the whole
  season means using March information. Its numbers look excellent and mean nothing as a
  forecast. It is shown because it is the model that runs the bracket, and hiding it
  would be worse than labelling it.

Once the pipeline has run through a full season, the ratings table carries a rating
snapshot for every date, and the blended model can be scored honestly too.

<DataTable data={model_summary} rows=5>
    <Column id=model_name title="Model" />
    <Column id=is_point_in_time title="Real forecast?" />
    <Column id=games title="Games" fmt='#,##0' />
    <Column id=accuracy title="Accuracy" fmt='pct1' />
    <Column id=log_loss title="Log loss" fmt='0.000' />
    <Column id=brier_score title="Brier" fmt='0.000' />
    <Column id=margin_error title="Margin error" fmt='0.0' />
</DataTable>

Accuracy is the least informative column. A model that picks the favourite in every game
scores well on it and has told you nothing. **Log loss** and **Brier score** are proper
scoring rules: they reward confidence only when it is justified, and punish confident
mistakes hard. A coin flip scores 0.693 and 0.25 respectively.

## Calibration

The question that decides whether the tournament odds mean anything: when the model says
70%, does it happen 70% of the time? A model can rank teams perfectly and still be
badly calibrated, and a bracket built on overconfident numbers looks far more certain
than the tournament actually is.

The diagonal is perfect calibration. Above it the model is underconfident; below it,
overconfident.

```sql calibration
select
    model_name,
    bucket_label,
    bucket_floor_pct,
    mean_predicted_probability,
    observed_win_rate,
    calibration_error,
    games
from model_calibration
where games >= 30
order by bucket_floor_pct
```

<LineChart
    data={calibration}
    x=mean_predicted_probability
    y=observed_win_rate
    series=model_name
    title="Predicted probability against observed win rate"
    xFmt='pct0'
    yFmt='pct0'
    xAxisTitle="What the model said"
    yAxisTitle="What actually happened"
/>

```sql calibration_table
select
    bucket_label,
    model_name,
    games,
    mean_predicted_probability,
    observed_win_rate,
    calibration_error
from model_calibration
where games >= 30
order by bucket_floor_pct, model_name
```

<DataTable data={calibration_table} groupBy=bucket_label rows=20>
    <Column id=model_name title="Model" />
    <Column id=games title="Games" fmt='#,##0' />
    <Column id=mean_predicted_probability title="Predicted" fmt='pct1' />
    <Column id=observed_win_rate title="Observed" fmt='pct1' />
    <Column id=calibration_error title="Error" fmt='+0.0%;-0.0%' contentType=colorscale />
</DataTable>

## Where the model struggles

Not every game is equally predictable. Conference tournament games pit teams from the
same league against each other at neutral sites, which strips out most of what a rating
knows — and the numbers show it.

```sql by_type
select
    game_type,
    model_name,
    sum(games_scored) as games,
    sum(accuracy * games_scored) / sum(games_scored) as accuracy,
    sum(log_loss * games_scored) / sum(games_scored) as log_loss
from model_accuracy
where is_point_in_time
group by game_type, model_name
order by game_type, log_loss
```

<DataTable data={by_type} groupBy=game_type rows=12>
    <Column id=model_name title="Model" />
    <Column id=games title="Games" fmt='#,##0' />
    <Column id=accuracy title="Accuracy" fmt='pct1' />
    <Column id=log_loss title="Log loss" fmt='0.000' contentType=colorscale colorScale=negative />
</DataTable>

## Accuracy by season

```sql by_season
select
    season,
    model_name,
    sum(games_scored) as games,
    sum(accuracy * games_scored) / sum(games_scored) as accuracy,
    sum(log_loss * games_scored) / sum(games_scored) as log_loss
from model_accuracy
where is_point_in_time
group by season, model_name
order by season
```

<LineChart
    data={by_season}
    x=season
    y=accuracy
    series=model_name
    title="Straight-up accuracy by season (point-in-time models only)"
    yFmt='pct0'
/>
