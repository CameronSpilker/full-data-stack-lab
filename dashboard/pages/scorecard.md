---
title: Team scorecard
---

Every number that decides whether a team is any good, on one screen. Pick a team.
It opens on BYU.

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
    games_vs_top_50,
    last_10_wins,
    last_10_games,
    -- How many teams a rank is out of. Counted rather than written down, so a
    -- season that adds or loses a team does not make the page wrong.
    --
    -- Every rank below is handed to BigValue as this integer with an explicit
    -- format, never as a string built here. A column like '#24 of 365' looks
    -- like the tidier option and is not: Evidence infers a format for the
    -- column it is given, and on a string of that shape it infers a numeric
    -- one and renders '#24.0 of 365.0'.
    (
        select count(*) from team_season
        where season = (select max(season) from team_season)
    ) as field_size
from team_season
where team_id::varchar = (select team_id from ${chosen})
    and season = (select max(season) from team_season)
```

# <Value data={team} column=team_name />

<Value data={team} column=conference_name /> · <Value data={team} column=record /> overall
· <Value data={team} column=conference_record /> in conference · ranked
<Value data={team} column=national_rank fmt='0' /> of <Value data={team} column=field_size fmt='0' />
nationally and <Value data={team} column=conference_rank fmt='0' /> in the league
· <Value data={team} column=season fmt='0000' /> season

<Grid cols=4>
    <BigValue
        data={team}
        value=adjusted_efficiency_margin
        title="Net efficiency"
        fmt='+0.0'
        comparison=national_rank
        comparisonFmt='0'
        comparisonDelta=false
        comparisonTitle="nationally"
        description="Points scored minus points allowed per 100 possessions, adjusted for the quality of the opponent. Every other number on this page is context for this one."
    />
    <BigValue
        data={team}
        value=adjusted_offensive_efficiency
        title="Offense"
        fmt='0.0'
        comparison=offense_rank
        comparisonFmt='0'
        comparisonDelta=false
        comparisonTitle="nationally for scoring"
        description="Points scored per 100 possessions, opponent adjusted."
    />
    <BigValue
        data={team}
        value=adjusted_defensive_efficiency
        title="Defense"
        fmt='0.0'
        comparison=defense_rank
        comparisonFmt='0'
        comparisonDelta=false
        comparisonTitle="nationally for conceding"
        description="Points allowed per 100 possessions, opponent adjusted. Lower is better."
    />
    <BigValue
        data={team}
        value=strength_of_schedule
        title="Schedule faced"
        fmt='0.0'
        comparison=schedule_strength_rank
        comparisonFmt='0'
        comparisonDelta=false
        comparisonTitle="hardest nationally"
        description="Average opponent quality. A rating built on nobody is a rating built on nothing."
    />
</Grid>

```sql elo_recent
-- The sparkline under the Elo tile, and the value it prints: BigValue shows the
-- last row, so this is ordered oldest first and cut to the last twenty games.
select game_date, elo_after
from (
    select game_date, elo_after
    from elo_timeline
    where team_id::varchar = (select team_id from ${chosen})
        and season = (select max(season) from elo_timeline)
    order by game_date desc
    limit 20
)
order by game_date
```

<Grid cols=4>
    <BigValue
        data={elo_recent}
        value=elo_after
        title="Elo, last twenty games"
        fmt='#,##0'
        sparkline=game_date
        sparklineColor=viz-model
        description="A running rating that moves with every result: up for a win, further up for beating someone good."
    />
    <BigValue
        data={team}
        value=adjusted_tempo
        title="Tempo"
        fmt='0.0'
        comparison=tempo_rank
        comparisonFmt='0'
        comparisonDelta=false
        comparisonTitle="fastest nationally"
        description="Possessions per 40 minutes. Neither fast nor slow is better, but it shapes every other number."
    />
    <BigValue
        data={team}
        value=wins_vs_top_50
        title="Wins vs top 50"
        fmt='0'
        comparison=games_vs_top_50
        comparisonFmt='0'
        comparisonDelta=false
        comparisonTitle="games against them"
    />
    <BigValue
        data={team}
        value=last_10_wins
        title="Won of the last ten"
        fmt='0'
        comparison=last_10_games
        comparisonFmt='0'
        comparisonDelta=false
        comparisonTitle="games played"
    />
</Grid>

## Where they stand

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

```sql four_factors
-- The four factors, plus what the defence does about them, as percentiles
-- rather than raw values. The underlying columns are not on one scale (a
-- turnover rate is a fraction, a rebound rate is a percentage), and a
-- percentile is what a reader wants from them anyway. Direction is applied
-- here: for turnovers committed and shooting allowed, lower is better.
with season as (
    select *
    from team_season
    where season = (select max(season) from team_season)
),

ranked as (
    select
        team_id,
        percent_rank() over (order by effective_fg_pct) as shooting,
        percent_rank() over (order by turnover_pct desc) as ball_security,
        percent_rank() over (order by offensive_rebound_pct) as offensive_boards,
        percent_rank() over (order by free_throw_rate) as free_throws,
        percent_rank() over (order by effective_fg_pct_allowed desc) as shooting_allowed,
        percent_rank() over (order by turnover_pct_forced) as turnovers_forced,
        percent_rank() over (order by defensive_rebound_pct) as defensive_boards
    from season
),

subject as (
    select * from ranked
    where team_id::varchar = (select team_id from ${chosen})
)

select factor, percentile from (
    select 'Shooting' as factor, shooting as percentile, 1 as ordering from subject
    union all select 'Ball security', ball_security, 2 from subject
    union all select 'Offensive boards', offensive_boards, 3 from subject
    union all select 'Free throw rate', free_throws, 4 from subject
    union all select 'Shooting allowed', shooting_allowed, 5 from subject
    union all select 'Turnovers forced', turnovers_forced, 6 from subject
    union all select 'Defensive boards', defensive_boards, 7 from subject
)
order by ordering
```

<Grid cols=2>
    <BarChart
        data={percentiles}
        x=measure
        y=percentile
        swapXY=true
        sort=false
        yFmt='pct0'
        yMin=0
        yMax=1
        yGridlines=false
        labels=true
        labelFmt='pct0'
        chartAreaHeight=220
        title="Rank as a position"
        subtitle="Percentile among all Division I teams. Higher is better on every row, schedule included."
    />
    <BarChart
        data={four_factors}
        x=factor
        y=percentile
        swapXY=true
        sort=false
        yFmt='pct0'
        yMin=0
        yMax=1
        yGridlines=false
        labels=true
        labelFmt='pct0'
        chartAreaHeight=220
        title="The four factors, both ends"
        subtitle="Shooting, turnovers, rebounding and free throws decide games. Percentile, direction applied, so higher is always better."
    />
</Grid>

## The season as it happened

Elo after every game. The level says how good they are. The slope says whether they
are getting there.

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
    lineColor=viz-model
    lineWidth=2
    markers=false
    chartAreaHeight=220
    title="Elo rating through the season"
/>

## Form and March

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

```sql rounds
select round, probability from (
    select 'Round of 32' as round, reached_round_of_32 as probability, 1 as step
    from tournament_odds where team_id::varchar = (select team_id from ${chosen})
    union all
    select 'Sweet 16', reached_sweet_16, 2
    from tournament_odds where team_id::varchar = (select team_id from ${chosen})
    union all
    select 'Elite Eight', reached_elite_eight, 3
    from tournament_odds where team_id::varchar = (select team_id from ${chosen})
    union all
    select 'Final Four', reached_final_four, 4
    from tournament_odds where team_id::varchar = (select team_id from ${chosen})
    union all
    select 'Title game', reached_championship_game, 5
    from tournament_odds where team_id::varchar = (select team_id from ${chosen})
    union all
    select 'Champion', won_championship, 6
    from tournament_odds where team_id::varchar = (select team_id from ${chosen})
)
order by step
```

<Grid cols=2>
    <BarChart
        data={form}
        x=game_date
        y=margin
        series=result
        seriesColors={{Won: 'positive', Lost: 'negative'}}
        yAxisTitle="Margin"
        chartAreaHeight=200
        title="The last ten games"
        subtitle="Height is the winning or losing margin. Colour and the legend both say which."
    />
    <BarChart
        data={rounds}
        x=round
        y=probability
        sort=false
        yFmt='pct1'
        labels=true
        labelFmt='pct1'
        chartAreaHeight=200
        title="How far the simulations take them"
        subtitle="Share of 20,000 simulated brackets reaching each round. Empty if the projected field does not include them."
    />
</Grid>

{#if odds.length > 0}

Projected a <Value data={odds} column=seed /> seed in the
<Value data={odds} column=region_name /> region.

<Grid cols=4>
    <BigValue data={odds} value=reached_sweet_16 title="Sweet 16" fmt='pct1' />
    <BigValue data={odds} value=reached_final_four title="Final Four" fmt='pct1' />
    <BigValue data={odds} value=won_championship title="Title" fmt='pct1' />
    <BigValue data={odds} value=expected_wins title="Expected wins" fmt='0.00' />
</Grid>

{:else}

Not in the projected field. The [bracket page](/bracket) has the 64 teams that are.

{/if}

## Good offense or good defense

Every Division I team placed by what they do at each end, with this team marked.
Defense is inverted, so up and to the right is good at both.

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
    seriesColors={{'Every other team': 'viz-muted'}}
    yInverted=true
    xAxisTitle="Adjusted offense (points per 100)"
    yAxisTitle="Adjusted defense (points allowed per 100)"
    chartAreaHeight=280
    tooltipTitle=team_name
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
