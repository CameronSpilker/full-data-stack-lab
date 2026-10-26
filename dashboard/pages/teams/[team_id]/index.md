<script>
    import AwaitingData from '$lib/AwaitingData.svelte';
</script>

# ${params.team_id}

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
    last_10_games,
    effective_fg_pct,
    effective_fg_pct_allowed,
    turnover_pct,
    turnover_pct_forced,
    offensive_rebound_pct,
    defensive_rebound_pct,
    three_point_pct
from team_season
where team_id = '${params.team_id}'
    and season = (select max(season) from team_season)
```

# <Value data={team} column=team_name />

<Value data={team} column=conference_name /> · <Value data={team} column=record /> overall
· <Value data={team} column=conference_record /> in conference · ranked
<Value data={team} column=national_rank /> nationally

<BigValue data={team} value=adjusted_efficiency_margin title="Net efficiency" fmt='+0.0;-0.0' />
<BigValue data={team} value=adjusted_offensive_efficiency title="Offense" fmt='0.0' />
<BigValue data={team} value=adjusted_defensive_efficiency title="Defense" fmt='0.0' />
<BigValue data={team} value=adjusted_tempo title="Tempo" fmt='0.0' />
<BigValue data={team} value=elo_rating title="Elo" fmt='#,##0' />
<BigValue data={team} value=strength_of_schedule title="Schedule strength" fmt='+0.0;-0.0' />

```sql season_status
select
    schedule_season_label,
    data_season_label,
    awaited_season_label,
    phase,
    next_game_date,
    last_completed_game_date
from season_status
```

{#if season_status[0].phase === 'preseason'}

<Alert status="warning">
The <Value data={season_status} column=schedule_season_label /> season has not
tipped off, so this page shows <Value data={season_status} column=data_season_label />.
</Alert>

{/if}

## Season by season

```sql history
select
    season,
    (season - 1)::varchar || '-' || right(season::varchar, 2) as season_label,
    conference_name,
    record,
    national_rank,
    adjusted_efficiency_margin,
    elo_rating,
    made_ncaa_tournament
from team_season
where team_id = '${params.team_id}'
order by season desc
```

<DataTable data={history} rows=10>
    <Column id=season_label title="Season" />
    <Column id=conference_name title="Conference" />
    <Column id=record title="Record" />
    <Column id=national_rank title="Rank" />
    <Column id=adjusted_efficiency_margin title="Net eff." fmt='+0.0;-0.0' contentType=colorscale />
    <Column id=elo_rating title="Elo" fmt='#,##0' />
    <Column id=made_ncaa_tournament title="NCAA" />
</DataTable>

## This season, game by game

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
where team_id = '${params.team_id}'
    and season = (select max(season) from elo_timeline)
order by game_date
```

<LineChart
    data={timeline}
    x=game_date
    y=elo_after
    title="Elo rating through the season"
    yAxisTitle="Elo"
/>

## Four factors

```sql factors
select 'Effective FG%' as factor, effective_fg_pct as offense, effective_fg_pct_allowed as defense
from team_season where team_id = '${params.team_id}' and season = (select max(season) from team_season)
union all
select 'Turnover %', turnover_pct, turnover_pct_forced
from team_season where team_id = '${params.team_id}' and season = (select max(season) from team_season)
union all
select 'Rebound %', offensive_rebound_pct, defensive_rebound_pct
from team_season where team_id = '${params.team_id}' and season = (select max(season) from team_season)
```

<DataTable data={factors} rows=4>
    <Column id=factor title="Factor" />
    <Column id=offense title="Offense" fmt='0.0' />
    <Column id=defense title="Defense" fmt='0.0' />
</DataTable>

```sql odds
select seed, region_name
from tournament_odds
where team_id = '${params.team_id}'
```

{#if odds.length > 0}

Projected a <Value data={odds} column=seed /> seed in the
<Value data={odds} column=region_name /> region. Its odds are on the
[March Madness](/march-madness) page.

{/if}

## What is next

```sql next_games
select
    game_date,
    case
        when home_team_id = '${params.team_id}' then away_team_name
        else home_team_name
    end as opponent_name,
    case
        when is_neutral_site then 'Neutral'
        when home_team_id = '${params.team_id}' then 'Home'
        else 'Away'
    end as site,
    case
        when home_team_id = '${params.team_id}' then home_win_probability
        else away_win_probability
    end as win_probability,
    case
        when market_home_win_probability is null then null
        when home_team_id = '${params.team_id}' then market_home_win_probability
        else 1 - market_home_win_probability
    end as market_probability,
    case
        when home_team_id = '${params.team_id}' then predicted_home_margin
        else -predicted_home_margin
    end as predicted_margin
from upcoming_games
where home_team_id = '${params.team_id}'
    or away_team_id = '${params.team_id}'
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
    detail="This team's next ten fixtures, priced. Fills in when the schedule does."
    height={180}
/>

{/if}

## Game log

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
where team_id = '${params.team_id}'
    and season = (select max(season) from elo_timeline)
order by game_date desc
```

<DataTable data={games} rows=20 search=true>
    <Column id=game_date title="Date" fmt='mmm d' />
    <Column id=opponent_name title="Opponent" />
    <Column id=result title="" />
    <Column id=margin title="Margin" fmt='+0;-0' contentType=colorscale />
    <Column id=site title="Site" />
    <Column id=pregame_win_probability title="Pregame odds" fmt='pct0' />
    <Column id=elo_change title="Elo +/-" fmt='+0.0;-0.0' />
</DataTable>
