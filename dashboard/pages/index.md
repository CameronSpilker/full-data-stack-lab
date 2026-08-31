---
title: NCAA Division I Men's Basketball
---

<Alert status="warning">

The numbers on this dashboard are currently <strong>synthetic</strong>, produced by
<code>ingest demo</code>, which simulates whole seasons so the pipeline runs without
network access. The teams are invented — no real program appears anywhere in it. Run
<code>ingest all</code> against the live APIs to replace them.

</Alert>

Tracking every Division I team through the season, and simulating the tournament
at the end of it.

```sql current
select max(season) as season from team_season
```

```sql totals
select
    count(*) as teams,
    count(distinct conference_name) as conferences,
    sum(games_played) / 2 as games,
    max(adjusted_efficiency_margin) as best_margin
from team_season
where season = (select max(season) from team_season)
```

```sql games_played
select count(*) as games from game_results
where season = (select max(season) from game_results)
```

<BigValue data={totals} value=teams title="Teams tracked" />
<BigValue data={totals} value=conferences title="Conferences" />
<BigValue data={games_played} value=games title="Games this season" fmt='#,##0' />
<BigValue data={current} value=season title="Season" />

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
    <Column id=adjusted_efficiency_margin title="Net eff." fmt='+0.0' contentType=colorscale />
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
    national_rank
from team_season
where season = (select max(season) from team_season)
```

<ScatterPlot
    data={quadrant}
    x=adjusted_offensive_efficiency
    y=adjusted_defensive_efficiency
    series=conference_name
    xAxisTitle="Adjusted offense (points per 100)"
    yAxisTitle="Adjusted defense (points allowed per 100)"
    yInverted=true
    legend=false
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
