---
title: How good is the model?
---

<script>
    import ViewNav from '$lib/ViewNav.svelte';
</script>

<ViewNav current="model" />

How often the predictor is right, and whether its confidence means anything.

## The three models

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

- **`elo_pregame`**: a real forecast, built only from games already played.
- **`market_consensus`**: the betting market's closing line. The benchmark to beat.
- **`blended_season_ratings`**: the full model, scored with end-of-season ratings,
  so it saw the future. Shown because it runs the bracket, not as a forecast.

<DataTable data={model_summary} rows=5>
    <Column id=model_name title="Model" />
    <Column id=is_point_in_time title="Real forecast?" />
    <Column id=games title="Games" fmt='#,##0' />
    <Column id=accuracy title="Accuracy" fmt='pct1' />
    <Column id=log_loss title="Log loss" fmt='0.000' />
    <Column id=brier_score title="Brier" fmt='0.000' />
    <Column id=margin_error title="Margin error" fmt='0.0' />
</DataTable>

Log loss and Brier reward confidence only when it is earned. A coin flip scores
0.693 and 0.25.

## Calibration

When the model says 70%, does it happen 70% of the time? On the diagonal is
perfect; below it is overconfident.

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

Conference tournaments are the hardest: same-league teams at neutral sites.

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
