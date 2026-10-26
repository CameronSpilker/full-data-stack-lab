---
title: Teams
---

<script>
    import AwaitingData from '$lib/AwaitingData.svelte';
    import ViewNav from '$lib/ViewNav.svelte';
    import TeamCrest from '$lib/TeamCrest.svelte';
</script>

<ViewNav current="scorecard" />

One team, one season. It opens on BYU in the latest season.

```sql seasons
select
    season,
    (season - 1)::varchar || '-' || right(season::varchar, 2) as season_label
from team_season
-- Only seasons with ratings: without them the ranks and charts are empty.
where adjusted_efficiency_margin is not null
group by season
order by season desc
```

```sql season_pick
select coalesce(
    try_cast(nullif('${inputs.season.value}', '') as integer),
    (select max(season) from team_season where adjusted_efficiency_margin is not null)
) as season
```

```sql teams
select
    team_id,
    team_name,
    conference_name
from team_season
where season = (select season from ${season_pick})
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

<div class="pickers">
<Dropdown
    data={seasons}
    name=season
    value=season
    label=season_label
    title="Season"
    defaultValue={seasons[0]?.season}
/>
<Dropdown
    data={teams}
    name=team
    value=team_id
    label=team_name
    title="Team"
    defaultValue={default_team[0]?.team_id}
/>
</div>

```sql team
select
    team_id,
    team_name,
    -- Nullable, both of them. The crest falls back to the team's initials
    -- when there is no mirrored logo, which is every team in the synthetic
    -- demo seasons.
    team_logo_url,
    team_color,
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
        where season = (select season from ${season_pick})
    ) as field_size
from team_season
where team_id::varchar = (select team_id from ${chosen})
    and season = (select season from ${season_pick})
```

<div class="masthead">
<TeamCrest
    teamId={team[0]?.team_id}
    name={team[0]?.team_name}
    color={team[0]?.team_color}
    size={64}
/>
<div>

# <Value data={team} column=team_name />

<Value data={team} column=conference_name /> · <Value data={team} column=record /> overall
· <Value data={team} column=conference_record /> in conference · ranked
<Value data={team} column=national_rank fmt='0' /> of <Value data={team} column=field_size fmt='0' />
nationally and <Value data={team} column=conference_rank fmt='0' /> in the league
· <Value data={team} column=wins_vs_top_50 fmt='0' /> wins from
<Value data={team} column=games_vs_top_50 fmt='0' /> games against the top 50
· <Value data={team} column=season fmt='0000' /> season

</div>
</div>

```sql verdict
-- The one-sentence read on the team, assembled in SQL rather than written in
-- the page, so it describes whichever team the dropdown is on.
--
-- Every band below is a cut on the team's own rank within the field, counted
-- rather than written down, so a season that gains or loses teams does not
-- quietly move the boundaries. The wording is deliberately plain: this is the
-- line someone repeats after closing the page.
with sized as (
    select
        national_rank,
        offense_rank,
        defense_rank,
        adjusted_efficiency_margin,
        last_10_wins,
        last_10_games,
        (select count(*) from team_season
         where season = (select season from ${season_pick})) as field_size
    from team_season
    where team_id::varchar = (select team_id from ${chosen})
        and season = (select season from ${season_pick})
)
select
    national_rank,
    field_size,
    adjusted_efficiency_margin,
    case
        when national_rank <= 16 then 'a genuine title contender'
        when national_rank <= 48 then 'good enough to make a deep run'
        when national_rank <= 100 then 'in the conversation, and inconsistent'
        when national_rank <= field_size / 2 then 'in the top half of the country'
        else 'below the national average'
    end as standing,
    -- Which side of the ball carries them, decided by the gap between the two
    -- ranks rather than by which is lower: a team ranked 20th on offence and
    -- 22nd on defence is balanced, not an offensive team.
    case
        when abs(offense_rank - defense_rank) <= 25 then 'balanced at both ends'
        when offense_rank < defense_rank then 'carried by its offence'
        else 'carried by its defence'
    end as shape,
    last_10_wins,
    last_10_games
from sized
```

<div class="verdict">
The model has this team <strong><Value data={verdict} column=standing /></strong>,
ranked <Value data={verdict} column=national_rank fmt='0' /> of
<Value data={verdict} column=field_size fmt='0' /> at
<Value data={verdict} column=adjusted_efficiency_margin fmt='+0.0' /> points per
100 possessions, and <Value data={verdict} column=shape />. It has won
<Value data={verdict} column=last_10_wins fmt='0' /> of its last
<Value data={verdict} column=last_10_games fmt='0' />.
</div>

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
        and season = (select season - 1 from ${season_pick})
),

-- Schedule strength is on a different scale in team_season, so the comparison
-- is built from the same opponent Elo the tile shows.
prior_opponents as (
    select avg(opponent_elo_before) as opponent_elo
    from elo_timeline
    where team_id::varchar = (select team_id from ${chosen})
        and season = (select season - 1 from ${season_pick})
),

games as (
    select game_date, elo_after, margin, is_win, opponent_elo_before
    from elo_timeline
    where team_id::varchar = (select team_id from ${chosen})
        and season = (select season from ${season_pick})
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
        description="A rating that moves with every result and carries across seasons."
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
        description="Average margin over the last ten games."
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
        description="Share of the last ten games won."
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
        description="Average rating of the last ten opponents. Higher is a harder run of games."
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
        description="Points scored minus allowed per 100 possessions, opponent adjusted."
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
        value=adjusted_tempo
        title="Tempo"
        fmt='0.0'
        comparison=tempo_rank
        comparisonFmt='0'
        comparisonDelta=false
        comparisonTitle="fastest nationally"
        description="Possessions per 40 minutes."
    />
</Grid>

Top row: the last ten games against last season. Bottom row: the season's
opponent-adjusted ratings and their national rank.

## Where they stand

```sql percentiles
with field as (
    select count(*) as teams
    from team_season
    where season = (select season from ${season_pick})
),

subject as (
    select *
    from team_season
    where team_id::varchar = (select team_id from ${chosen})
        and season = (select season from ${season_pick})
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
    where season = (select season from ${season_pick})
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
        subtitle="Percentile among Division I teams. Higher is better."
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
        subtitle="Percentile, so higher is always better."
    />
</Grid>

## The season as it happened

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
    and season = (select season from ${season_pick})
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

## Every season on record

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
    subtitle="1500 is an average Division I team. Flat stretches are summers."
/>

<Grid cols=4>
    <BigValue data={program_span} value=seasons title="Seasons on record" fmt='0' />
    <BigValue data={program_span} value=games title="Games played" fmt='#,##0' />
    <BigValue data={program_span} value=highest title="Best Elo reached" fmt='#,##0' />
    <BigValue data={program_span} value=lowest title="Lowest Elo reached" fmt='#,##0' />
</Grid>

## The last ten games

```sql form
select
    game_date,
    opponent_name,
    margin,
    case when is_win then 'Won' else 'Lost' end as result,
    pregame_win_probability
from elo_timeline
where team_id::varchar = (select team_id from ${chosen})
    and season = (select season from ${season_pick})
order by game_date desc
limit 10
```

```sql in_field
-- Whether this team is in the projected field. The simulations themselves
-- live on the March Madness page.
select seed, region_name
from tournament_odds
where team_id::varchar = (select team_id from ${chosen})
    and season = (select season from ${season_pick})
```

{#if form.length > 0}
<BarChart
    data={form}
    x=game_date
    y=margin
    series=result
    seriesColors={{Won: 'positive', Lost: 'negative'}}
    yAxisTitle="Margin"
    chartAreaHeight=200
/>
{:else}
<AwaitingData
    title="The last ten games"
    detail="Fills in once this team has played."
    height={200}
/>
{/if}

{#if in_field.length > 0}

Projected a <Value data={in_field} column=seed /> seed in the
<Value data={in_field} column=region_name /> region. Its odds are on the
[March Madness](/march-madness) page.

{/if}

## Compare teams

```sql compare_options
select team_id, team_name
from team_season
where season = (select season from ${season_pick})
order by national_rank
```

<Dropdown
    data={compare_options}
    name=compare
    value=team_id
    label=team_name
    title="Teams"
    multiple=true
    defaultValue={compare_options.slice(0, 3).map((d) => d.team_id)}
/>

```sql compared
-- The chosen team plus whoever is picked here, or the top three when nothing
-- is. The pick is read out of a dollar-quoted string rather than spliced in
-- as a list, so the same SQL runs with a selection, an empty one, or none yet
-- while the page prerenders.
with picked as (
    select unnest(regexp_extract_all($$${inputs.compare.value}$$, '\b[1-9][0-9]*\b')) as team_id
),

shown as (
    select team_id from picked
    union
    select team_id::varchar from (
        select team_id from team_season
        where season = (select season from ${season_pick})
        order by national_rank
        limit 3
    )
    where not exists (select 1 from picked)
    union
    select team_id from ${chosen}
)

select
    team_id,
    team_name,
    national_rank,
    record,
    adjusted_efficiency_margin,
    adjusted_offensive_efficiency,
    adjusted_defensive_efficiency,
    adjusted_tempo,
    elo_rating,
    schedule_strength_rank
from team_season
where season = (select season from ${season_pick})
    and team_id::varchar in (select team_id from shown)
order by national_rank
```

```sql compared_elo
select e.game_date, e.team_name, e.elo_after
from elo_timeline as e
where e.season = (select season from ${season_pick})
    and e.team_id::varchar in (select team_id::varchar from ${compared})
order by e.game_date
```

<LineChart
    data={compared_elo}
    x=game_date
    y=elo_after
    series=team_name
    yAxisTitle="Elo"
    markers=false
    chartAreaHeight=240
    title="Elo through the season"
/>

<DataTable data={compared} rows=10>
    <Column id=national_rank title="#" />
    <Column id=team_name title="Team" />
    <Column id=record title="Record" />
    <Column id=adjusted_efficiency_margin title="Net eff." fmt='+0.0;-0.0' contentType=colorscale />
    <Column id=adjusted_offensive_efficiency title="Off." fmt='0.0' />
    <Column id=adjusted_defensive_efficiency title="Def." fmt='0.0' />
    <Column id=adjusted_tempo title="Tempo" fmt='0.0' />
    <Column id=elo_rating title="Elo" fmt='#,##0' />
    <Column id=schedule_strength_rank title="SOS rank" />
</DataTable>

## What is next

The rest of this season's schedule. "Model" is this team's chance of winning,
"market" is the betting consensus.

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
where (home_team_id = (select team_id from ${chosen})
        or away_team_id = (select team_id from ${chosen}))
    and season = (select season from ${season_pick})
order by game_date
limit 10
```

{#if next_games.length > 0}

<DataTable data={next_games} rows=10>
    <Column id=game_date title="Date" fmt='mmm d' />
    <Column id=opponent_name title="Opponent" />
    <Column id=site title="Site" />
    <Column id=predicted_margin title="Model line" fmt='+0.0;-0.0' />
    <Column id=win_probability title="Model" fmt='pct0' contentType=colorscale />
    <Column id=market_probability title="Market" fmt='pct0' />
</DataTable>

{:else}

<AwaitingData
    title="The rest of the schedule, priced"
    detail="This team's next ten fixtures, priced. Empty for a finished season."
    height={180}
/>

{/if}

## Good offense or good defense

This team against the field. Up and to the right is good at both ends.

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
where season = (select season from ${season_pick})
-- The marked team is drawn last so it lands on top of the cloud rather than under it.
order by is_subject
```

<LogoScatter
    data={landscape}
    highlight={landscape.find((d) => d.is_subject === 1)?.team_name}
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

Ranked by how unlikely Elo thought each one was before tip-off.

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
    and season = (select season from ${season_pick})
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
    and season = (select season from ${season_pick})
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

<style>
    .pickers {
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
        align-items: flex-end;
        margin-bottom: 1rem;
    }

    .masthead {
        display: flex;
        gap: 1rem;
        align-items: center;
        margin-bottom: 0.5rem;
    }

    /* The heading already carries the page's top margin; inside the masthead
       it would push the crest out of line with the text beside it. */
    .masthead :global(h1) {
        margin-top: 0;
    }

    /* Derived from `currentColor` so the card follows the reader's appearance
       without naming a hex twice, the same rule the components keep. */
    .verdict {
        margin: 1rem 0 1.5rem;
        padding: 1rem 1.25rem;
        border: 1px solid color-mix(in srgb, currentColor 18%, transparent);
        border-radius: 0.375rem;
        background: color-mix(in srgb, currentColor 4%, transparent);
        font-size: 1.05rem;
        line-height: 1.55;
        max-width: 70ch;
    }

    @media (max-width: 40rem) {
        .masthead {
            gap: 0.75rem;
        }
    }
</style>
