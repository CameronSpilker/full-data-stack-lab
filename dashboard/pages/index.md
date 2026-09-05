---
title: NCAA Division I Men's Basketball
---

Tracking every Division I team through the season, and simulating the tournament
at the end of it. Every number here comes out of a tested dbt model:
[how it works](/how-it-works).

For one team on one screen, open the [team scorecard](/scorecard).

```sql current
select max(season) as season from team_season
```

```sql totals
select
    count(*) as teams,
    count(distinct conference_name) as conferences
from team_season
where season = (select max(season) from team_season)
```

```sql games_played
-- Played, not scheduled. Mid-season the schedule runs to about six thousand
-- games and only a fraction of them have happened.
select count(*) as games from game_results
where season = (select max(season) from game_results)
    and is_completed
```

<Grid cols=4>
    <BigValue data={totals} value=teams title="Division I teams" />
    <BigValue data={totals} value=conferences title="Conferences" />
    <BigValue data={games_played} value=games title="Games played" fmt='#,##0' />
    <!-- A season is a year, not a quantity, so it takes no thousands separator. -->
    <BigValue data={current} value=season title="Season" fmt='0000' />
</Grid>

## The top of the country

Ranked by adjusted efficiency margin — points scored minus points allowed per 100
possessions, adjusted for the quality of the opponent. It is the single best one-number
summary of how good a team is, and it is what the predictor runs on.

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
    elo_rating,
    strength_of_schedule
from team_season
where season = (select max(season) from team_season)
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

Every team placed by what it does on each end. Up and to the right is good at both —
the top left quadrant is elite offense, the bottom right elite defense. Teams furthest
from the centre in either direction are the ones with a real identity.

```sql quadrant
select
    team_name,
    conference_name,
    adjusted_offensive_efficiency,
    adjusted_defensive_efficiency,
    adjusted_efficiency_margin,
    national_rank,
    case when national_rank <= 25 then 'Top 25' else 'Everyone else' end as tier,
    -- The top 25 are drawn last so they land on top of the cloud.
    case when national_rank <= 25 then 1 else 0 end as is_top
from team_season
where season = (select max(season) from team_season)
order by is_top
```

<ScatterPlot
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

## Best of the season so far

The games the ratings said were least likely to go the way they did.

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
where season = (select max(season) from game_results)
    and elo_home_win_probability is not null
order by winner_pregame_probability
limit 10
```

<DataTable data={upsets} rows=10>
    <Column id=game_date title="Date" fmt='mmm d' />
    <Column id=winner title="Winner" />
    <Column id=loser title="Lost to" />
    <Column id=margin title="By" />
    <Column id=winner_pregame_probability title="Pregame odds" fmt='pct1' contentType=colorscale colorScale=negative />
</DataTable>
