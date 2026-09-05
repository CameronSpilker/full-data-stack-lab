---
title: Team scorecard
---

Every number that decides whether a team is any good, on one screen. Pick a team.
It opens on BYU.

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
tipped off.** Every number on this page describes <Value data={season_status} column=data_season_label />, the
last completed season, because a team that has not played a game cannot be rated,
ranked or seeded. <Value data={season_status} column=scheduled_games fmt='#,##0' />
games are on the schedule, the first of them
<Value data={season_status} column=next_game_date fmt='mmmm d' />.

The [upcoming picks](/picks) page is the one that has already moved on: a forecast
does not need results, so it is pricing those fixtures now.

</Alert>

{/if}

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
· <Value data={team} column=wins_vs_top_50 fmt='0' /> wins from
<Value data={team} column=games_vs_top_50 fmt='0' /> games against the top 50
· <Value data={team} column=season fmt='0000' /> season

```sql form_trend
-- The four trend tiles read this one result, so they all share a row 0 and
-- cannot disagree about which game is the latest.
--
-- Ordered newest first on purpose. BigValue prints `data[0]`, not the last row,
-- so an oldest-first ordering would headline the value from ten games ago. The
-- sparkline is unaffected: it sorts by its own date column before drawing.
--
-- Every delta is against the same team's previous season. Elo carries across
-- seasons rather than resetting, so last season's closing rating is the honest
-- thing to measure this season's against. The other three are season aggregates
-- the warehouse has held for every season since 2022.
with prior as (
    select elo_rating, win_pct, avg_margin
    from team_season
    where team_id::varchar = (select team_id from ${chosen})
        and season = (select max(season) - 1 from team_season)
),

-- Schedule strength is on a different scale in team_season, so the comparison
-- is built from the same opponent Elo the tile shows.
prior_opponents as (
    select avg(opponent_elo_before) as opponent_elo
    from elo_timeline
    where team_id::varchar = (select team_id from ${chosen})
        and season = (select max(season) - 1 from elo_timeline)
),

games as (
    select game_date, elo_after, margin, is_win, opponent_elo_before
    from elo_timeline
    where team_id::varchar = (select team_id from ${chosen})
        and season = (select max(season) from elo_timeline)
),

-- Ten games is the window the rest of the page already uses for form. Early in
-- a season the frame is shorter than ten, which is the correct behaviour: it
-- averages what has been played rather than padding with nothing.
rolled as (
    select
        game_date,
        elo_after,
        avg(margin)
            over (order by game_date rows between 9 preceding and current row) as margin_10,
        avg(case when is_win then 1.0 else 0.0 end)
            over (order by game_date rows between 9 preceding and current row) as win_rate_10,
        avg(opponent_elo_before)
            over (order by game_date rows between 9 preceding and current row) as opponent_elo_10
    from games
)

select
    rolled.game_date,
    rolled.elo_after,
    rolled.margin_10,
    rolled.win_rate_10,
    rolled.opponent_elo_10,
    rolled.elo_after - prior.elo_rating as elo_vs_last,
    rolled.margin_10 - prior.avg_margin as margin_vs_last,
    rolled.win_rate_10 - prior.win_pct as win_rate_vs_last,
    rolled.opponent_elo_10 - prior_opponents.opponent_elo as opponent_elo_vs_last
from rolled
-- Left joins, because a team in its first Division I season has no previous
-- one. The deltas come back null and the tiles render without them.
left join prior on true
left join prior_opponents on true
order by rolled.game_date desc
```

<Grid cols=4>
    <BigValue
        data={form_trend}
        value=elo_after
        title="Elo"
        fmt='#,##0'
        sparkline=game_date
        sparklineColor=viz-model
        comparison=elo_vs_last
        comparisonFmt='+#,##0;-#,##0'
        comparisonTitle="vs last season"
        description="A running rating that moves with every result: up for a win, further up for beating someone good. It carries across seasons rather than resetting, so last season's closing rating is what this is measured against."
    />
    <BigValue
        data={form_trend}
        value=margin_10
        title="Scoring margin, last ten"
        fmt='+0.0;-0.0'
        sparkline=game_date
        sparklineColor=viz-model
        comparison=margin_vs_last
        comparisonFmt='+0.0;-0.0'
        comparisonTitle="vs last season"
        description="Average points won or lost by across the last ten games, against the same team's average for all of last season."
    />
    <BigValue
        data={form_trend}
        value=win_rate_10
        title="Win rate, last ten"
        fmt='pct0'
        sparkline=game_date
        sparklineColor=viz-model
        comparison=win_rate_vs_last
        comparisonFmt='+0%;-0%'
        comparisonTitle="vs last season"
        description="Share of the last ten games won, against last season's rate across every game."
    />
    <BigValue
        data={form_trend}
        value=opponent_elo_10
        title="Opponent Elo, last ten"
        fmt='#,##0'
        sparkline=game_date
        sparklineColor=viz-model
        comparison=opponent_elo_vs_last
        comparisonFmt='+#,##0;-#,##0'
        comparisonTitle="vs last season"
        description="Average rating of the last ten opponents. Higher is a harder run of games, not a better team, so read it beside the three tiles to its left rather than on its own."
    />
</Grid>

<Grid cols=4>
    <BigValue
        data={team}
        value=adjusted_efficiency_margin
        title="Net efficiency"
        fmt='+0.0;-0.0'
        comparison=national_rank
        comparisonFmt='0'
        comparisonDelta=false
        comparisonTitle="nationally"
        description="Points scored minus points allowed per 100 possessions, adjusted for the quality of the opponent. The single best one number summary of how good a team is."
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
        description="Points allowed per 100 possessions, opponent adjusted. Lower is better, which is why the rank beside it and the number move in opposite directions."
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
        description="Possessions per 40 minutes. Neither fast nor slow is better, but it shapes every other number on this page."
    />
</Grid>

The top row is this season moving: each tile draws its own last ten games and
compares where the team is now against where they finished last season. The
bottom row is the opponent adjusted ratings, which the warehouse holds for this
season only, so they carry their national rank instead of a trend.

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

## Five seasons

```sql program
-- Every game the team has played in the warehouse, not just this season. Elo
-- carries across seasons rather than resetting, so this is one continuous line
-- and the gaps in it are summers.
select
    game_date,
    season,
    elo_after
from elo_timeline
where team_id::varchar = (select team_id from ${chosen})
order by game_date
```

```sql program_span
select
    min(season) as first_season,
    max(season) as last_season,
    count(distinct season) as seasons,
    count(*) as games,
    min(elo_after) as lowest,
    max(elo_after) as highest
from elo_timeline
where team_id::varchar = (select team_id from ${chosen})
```

Where the program has been, not just where it is. One line, every game since
<Value data={program_span} column=first_season fmt='0000' />: the flat stretches
are summers, and each climb or slide is a season. A team peaking is a line that
ends higher than the one before it started.

<LineChart
    data={program}
    x=game_date
    y=elo_after
    yAxisTitle="Elo"
    lineColor=viz-model
    lineWidth=2
    markers=false
    chartAreaHeight=260
    title="Elo across every season in the warehouse"
    subtitle="Higher is better. 1500 is an average Division I team, and the rating only moves when a game is played."
/>

<Grid cols=4>
    <BigValue data={program_span} value=seasons title="Seasons on record" fmt='0' />
    <BigValue data={program_span} value=games title="Games played" fmt='#,##0' />
    <BigValue data={program_span} value=highest title="Best Elo reached" fmt='#,##0' />
    <BigValue data={program_span} value=lowest title="Lowest Elo reached" fmt='#,##0' />
</Grid>

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

## What is next

The rest of the schedule, priced the same way the [upcoming picks](/picks) page
prices it. "Model" is this team's chance of winning, "market" is what the
betting consensus gives them, and a game with no market number is one no book
has posted yet.

```sql next_games
select
    game_date,
    case
        when home_team_id = (select team_id from ${chosen}) then away_team_name
        else home_team_name
    end as opponent_name,
    case
        when is_neutral_site then 'Neutral'
        when home_team_id = (select team_id from ${chosen}) then 'Home'
        else 'Away'
    end as site,
    case
        when home_team_id = (select team_id from ${chosen}) then home_win_probability
        else away_win_probability
    end as win_probability,
    case
        when market_home_win_probability is null then null
        when home_team_id = (select team_id from ${chosen}) then market_home_win_probability
        else 1 - market_home_win_probability
    end as market_probability,
    case
        when home_team_id = (select team_id from ${chosen}) then predicted_home_margin
        else -predicted_home_margin
    end as predicted_margin,
    days_out
from upcoming_games
where home_team_id = (select team_id from ${chosen})
    or away_team_id = (select team_id from ${chosen})
order by game_date
limit 10
```

<DataTable data={next_games} rows=10>
    <Column id=game_date title="Date" fmt='mmm d' />
    <Column id=opponent_name title="Opponent" />
    <Column id=site title="Site" />
    <Column id=predicted_margin title="Model line" fmt='+0.0;-0.0' />
    <Column id=win_probability title="Model" fmt='pct0' contentType=colorscale />
    <Column id=market_probability title="Market" fmt='pct0' />
</DataTable>

Empty means the season is over, or has not started. The schedule arrives with
the rest of the game feed, so a fixture appears here as soon as the source
carries it.

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
    <Column id=margin title="By" fmt='+0;-0' />
    <Column id=pregame_win_probability title="Pregame odds" fmt='pct0' contentType=colorscale colorScale=negative />
    <Column id=elo_change title="Elo +/-" fmt='+0.0;-0.0' />
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
    <Column id=margin title="Margin" fmt='+0;-0' contentType=colorscale />
    <Column id=site title="Site" />
    <Column id=pregame_win_probability title="Pregame odds" fmt='pct0' />
    <Column id=elo_change title="Elo +/-" fmt='+0.0;-0.0' />
</DataTable>
