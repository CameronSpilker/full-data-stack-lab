---
title: Team scorecard
---

One team, one page, the numbers that decide whether they are any good. Pick a team
below. It opens on BYU.

```sql teams
select
    team_id,
    team_name,
    conference_name
from team_season
where season = (select max(season) from team_season)
order by team_name
```

```sql default_team
-- What the page opens on. Deliberately independent of the dropdown: the
-- dropdown's default is read from here, so this query cannot depend on it
-- without the two waiting on each other. BYU, or the top ranked team if a
-- season ever arrives without them in it.
select coalesce(
    (
        select team_id::varchar
        from team_season
        where season = (select max(season) from team_season)
            and (team_name ilike '%BYU%' or team_name ilike 'Brigham Young%')
        limit 1
    ),
    (
        select team_id::varchar
        from team_season
        where season = (select max(season) from team_season)
        order by national_rank
        limit 1
    )
) as team_id
```

```sql chosen
-- Every query below reads its team from here, so there is one place that
-- decides it. Before anyone touches the dropdown, and while the page is being
-- prerendered with no inputs at all, that is the default above.
select coalesce(
    nullif(nullif('${inputs.team.value}', ''), 'undefined'),
    (select team_id from ${default_team})
) as team_id
```

<Dropdown
    data={teams}
    name=team
    value=team_id
    label=team_name
    title="Team"
    defaultValue={default_team[0]?.team_id}
/>

```sql team
select
    team_id,
    team_name,
    conference_name,
    season,
    record,
    conference_record,
    national_rank,
    conference_rank,
    adjusted_efficiency_margin,
    adjusted_offensive_efficiency,
    adjusted_defensive_efficiency,
    adjusted_tempo,
    offense_rank,
    defense_rank,
    tempo_rank,
    elo_rating,
    strength_of_schedule,
    schedule_strength_rank,
    wins_vs_top_50,
    last_10_wins,
    last_10_games
from team_season
where team_id::varchar = (select team_id from ${chosen})
    and season = (select max(season) from team_season)
```

# <Value data={team} column=team_name />

<Value data={team} column=conference_name /> · <Value data={team} column=record /> overall
· <Value data={team} column=conference_record /> in conference · ranked
<Value data={team} column=national_rank /> of 365 nationally, and
<Value data={team} column=conference_rank /> in the league

<BigValue data={team} value=adjusted_efficiency_margin title="Net efficiency" fmt='+0.0' />
<BigValue data={team} value=adjusted_offensive_efficiency title="Offense" fmt='0.0' />
<BigValue data={team} value=adjusted_defensive_efficiency title="Defense" fmt='0.0' />
<BigValue data={team} value=elo_rating title="Elo" fmt='#,##0' />
<BigValue data={team} value=adjusted_tempo title="Tempo" fmt='0.0' />
<BigValue data={team} value=wins_vs_top_50 title="Wins vs top 50" fmt='0' />

Net efficiency is points scored minus points allowed per 100 possessions, adjusted
for the quality of the opponent. Everything else on this page is context for that
one number.

## Where they stand

Percentile against every Division I team, so a rank reads as a position rather than
as a number you have to hold the field size in your head to interpret. Schedule
strength is included because a rating built on nobody is a rating built on nothing.

```sql percentiles
with field as (
    select count(*) as teams
    from team_season
    where season = (select max(season) from team_season)
),

subject as (
    select *
    from team_season
    where team_id::varchar = (select team_id from ${chosen})
        and season = (select max(season) from team_season)
)

select 'Net efficiency' as measure, subject.national_rank as rank,
    1.0 - (subject.national_rank - 1.0) / field.teams as percentile
from subject, field
union all
select 'Offense', subject.offense_rank,
    1.0 - (subject.offense_rank - 1.0) / field.teams
from subject, field
union all
select 'Defense', subject.defense_rank,
    1.0 - (subject.defense_rank - 1.0) / field.teams
from subject, field
union all
select 'Schedule faced', subject.schedule_strength_rank,
    1.0 - (subject.schedule_strength_rank - 1.0) / field.teams
from subject, field
```

<BarChart
    data={percentiles}
    x=measure
    y=percentile
    swapXY=true
    sort=false
    yFmt='pct0'
    yAxisTitle="Percentile among Division I"
    title="Percentile by measure, higher is better"
/>

## The season as it happened

Elo after every game. The level says how good they are. The slope says whether they
are getting there: a line climbing through February is a team peaking at the right
time, and a line sagging is a team that will be an early exit whatever the seed says.

```sql timeline
select
    game_date,
    game_number,
    elo_after,
    elo_change,
    opponent_name,
    is_win,
    margin,
    game_type
from elo_timeline
where team_id::varchar = (select team_id from ${chosen})
    and season = (select max(season) from elo_timeline)
order by game_date
```

<LineChart
    data={timeline}
    x=game_date
    y=elo_after
    yAxisTitle="Elo"
    title="Elo rating through the season"
/>

## Good offense or good defense

Every Division I team placed by what they do at each end, with this team marked.
Defense is inverted, so up and to the right is good at both. The teams in the top
right corner are the ones who win in March.

```sql landscape
select
    team_name,
    conference_name,
    adjusted_offensive_efficiency,
    adjusted_defensive_efficiency,
    case
        when team_id::varchar = (select team_id from ${chosen}) then team_name
        else 'Every other team'
    end as highlight,
    case when team_id::varchar = (select team_id from ${chosen}) then 1 else 0 end as is_subject
from team_season
where season = (select max(season) from team_season)
-- The marked team is drawn last so it lands on top of the cloud rather than under it.
order by is_subject
```

<ScatterPlot
    data={landscape}
    x=adjusted_offensive_efficiency
    y=adjusted_defensive_efficiency
    series=highlight
    yInverted=true
    xAxisTitle="Adjusted offense (points per 100)"
    yAxisTitle="Adjusted defense (points allowed per 100)"
    tooltipTitle=team_name
/>

## Form

The last ten games, by margin. Height is how much they won or lost by, and the
colour is which of the two it was.

```sql form
select
    game_date,
    opponent_name,
    margin,
    case when is_win then 'Won' else 'Lost' end as result,
    pregame_win_probability
from elo_timeline
where team_id::varchar = (select team_id from ${chosen})
    and season = (select max(season) from elo_timeline)
order by game_date desc
limit 10
```

<BarChart
    data={form}
    x=game_date
    y=margin
    series=result
    yAxisTitle="Margin"
    title="Last ten games"
/>

## The wins that count

Ranked by how unlikely the model thought each one was before tip-off. A team's best
result is not its biggest blowout, it is the game it had no business winning.

```sql best_wins
select
    game_date,
    opponent_name,
    margin,
    pregame_win_probability,
    elo_change,
    case when is_home then 'Home' when is_neutral_site then 'Neutral' else 'Away' end as site
from elo_timeline
where team_id::varchar = (select team_id from ${chosen})
    and season = (select max(season) from elo_timeline)
    and is_win
order by pregame_win_probability
limit 5
```

<DataTable data={best_wins} rows=5>
    <Column id=game_date title="Date" fmt='mmm d' />
    <Column id=opponent_name title="Beat" />
    <Column id=site title="Site" />
    <Column id=margin title="By" fmt='+0' />
    <Column id=pregame_win_probability title="Pregame odds" fmt='pct0' contentType=colorscale colorScale=negative />
    <Column id=elo_change title="Elo +/-" fmt='+0.0' />
</DataTable>

## March

```sql odds
select
    seed,
    region_name,
    reached_round_of_32,
    reached_sweet_16,
    reached_elite_eight,
    reached_final_four,
    reached_championship_game,
    won_championship,
    expected_wins
from tournament_odds
where team_id::varchar = (select team_id from ${chosen})
```

{#if odds.length > 0}

Projected a <Value data={odds} column=seed /> seed in the
<Value data={odds} column=region_name /> region, from 20,000 simulated brackets.

<BigValue data={odds} value=reached_sweet_16 title="Sweet 16" fmt='pct1' />
<BigValue data={odds} value=reached_final_four title="Final Four" fmt='pct1' />
<BigValue data={odds} value=won_championship title="Title" fmt='pct1' />
<BigValue data={odds} value=expected_wins title="Expected wins" fmt='0.00' />

```sql rounds
select 'Round of 32' as round, reached_round_of_32 as probability, 1 as step from tournament_odds where team_id::varchar = (select team_id from ${chosen})
union all
select 'Sweet 16', reached_sweet_16, 2 from tournament_odds where team_id::varchar = (select team_id from ${chosen})
union all
select 'Elite Eight', reached_elite_eight, 3 from tournament_odds where team_id::varchar = (select team_id from ${chosen})
union all
select 'Final Four', reached_final_four, 4 from tournament_odds where team_id::varchar = (select team_id from ${chosen})
union all
select 'Title game', reached_championship_game, 5 from tournament_odds where team_id::varchar = (select team_id from ${chosen})
union all
select 'Champion', won_championship, 6 from tournament_odds where team_id::varchar = (select team_id from ${chosen})
order by step
```

<BarChart
    data={rounds}
    x=round
    y=probability
    sort=false
    yFmt='pct1'
    yAxisTitle="Chance of reaching"
    title="How far the simulations take them"
/>

{:else}

Not in the projected field. The bracket page has the 64 teams that are.

{/if}

## Every game

```sql games
select
    game_date,
    opponent_name,
    case when is_win then 'W' else 'L' end as result,
    margin,
    case when is_home then 'Home' when is_neutral_site then 'Neutral' else 'Away' end as site,
    pregame_win_probability,
    elo_change,
    game_type
from elo_timeline
where team_id::varchar = (select team_id from ${chosen})
    and season = (select max(season) from elo_timeline)
order by game_date desc
```

<DataTable data={games} rows=12 search=true>
    <Column id=game_date title="Date" fmt='mmm d' />
    <Column id=opponent_name title="Opponent" />
    <Column id=result title="" />
    <Column id=margin title="Margin" fmt='+0' contentType=colorscale />
    <Column id=site title="Site" />
    <Column id=pregame_win_probability title="Pregame odds" fmt='pct0' />
    <Column id=elo_change title="Elo +/-" fmt='+0.0' />
</DataTable>
