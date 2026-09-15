---
title: Matchup
---

<script>
    import ViewNav from '$lib/ViewNav.svelte';
    import TeamCrest from '$lib/TeamCrest.svelte';
</script>

<ViewNav current="matchup" />

Any two teams in the country, priced at a neutral site. It opens on BYU against
the best team in the field.

```sql season_status
select
    schedule_season_label,
    data_season_label,
    phase
from season_status
```

{#if season_status[0].phase === 'preseason'}

<Alert status="warning">

**The <Value data={season_status} column=schedule_season_label /> season has not
tipped off.** Every price on this page is built from
<Value data={season_status} column=data_season_label /> ratings, because a team
that has not played a game cannot be rated. The numbers are real, and they are
about last season's teams.

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

```sql default_home
-- What the page opens on, independent of both dropdowns so that neither has to
-- wait on the other. BYU, or the top ranked team if a season ever arrives
-- without them in it. The same rule the scorecard uses, so the two pages agree
-- about whose season this site is mostly about.
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

```sql default_away
-- The best team that is not the home side, so the page opens on a game worth
-- looking at rather than on a mismatch.
select team_id::varchar as team_id
from team_season
where season = (select max(season) from team_season)
    and team_id::varchar != (select team_id from ${default_home})
order by national_rank
limit 1
```

```sql home_pick
select coalesce(
    nullif(nullif('${inputs.home.value}', ''), 'undefined'),
    (select team_id from ${default_home})
) as team_id
```

```sql away_pick
-- Falls back to the default when the reader picks the same team on both sides.
-- A team playing itself prices at exactly even, which looks like a bug in the
-- model rather than what it is, and the matchup grid has no such row to read.
select case
    when coalesce(
        nullif(nullif('${inputs.away.value}', ''), 'undefined'),
        (select team_id from ${default_away})
    ) = (select team_id from ${home_pick})
    then (
        select team_id::varchar
        from team_season
        where season = (select max(season) from team_season)
            and team_id::varchar != (select team_id from ${home_pick})
        order by national_rank
        limit 1
    )
    else coalesce(
        nullif(nullif('${inputs.away.value}', ''), 'undefined'),
        (select team_id from ${default_away})
    )
end as team_id
```

<div class="pickers">
<Dropdown
    data={teams}
    name=home
    value=team_id
    label=team_name
    title="Team"
    defaultValue={default_home[0]?.team_id}
/>
<Dropdown
    data={teams}
    name=away
    value=team_id
    label=team_name
    title="Opponent"
    defaultValue={default_away[0]?.team_id}
/>
</div>

```sql oriented
-- mart_matchup_odds stores each pair once, in team_id order, because a grid
-- holding every matchup both ways is twice the rows for none of the
-- information. Reading it from a chosen team's side means putting the mirror
-- back: the margin negates and each probability becomes one minus itself.
select
    team_id as side_id,
    opponent_team_id as other_id,
    predicted_margin_neutral as margin,
    predicted_margin_at_home as margin_at_home,
    win_probability_neutral as win_probability,
    win_probability_efficiency_only as efficiency_probability,
    win_probability_elo_only as elo_probability
from matchup_odds

union all

select
    opponent_team_id,
    team_id,
    -predicted_margin_neutral,
    -- The home column is the first team at home, so mirroring it means the
    -- other team is now the host: the sign flips and the advantage moves with
    -- it. Recomputed from the neutral margin rather than negated, which would
    -- hand the home side's 3.5 points to the visitor.
    -(predicted_margin_neutral) + (predicted_margin_at_home - predicted_margin_neutral),
    1 - win_probability_neutral,
    1 - win_probability_efficiency_only,
    1 - win_probability_elo_only
from matchup_odds
```

```sql matchup
select
    oriented.margin,
    oriented.margin_at_home,
    oriented.win_probability,
    oriented.efficiency_probability,
    oriented.elo_probability,
    abs(oriented.efficiency_probability - oriented.elo_probability) as disagreement,
    greatest(oriented.win_probability, 1 - oriented.win_probability)
        as favourite_probability,
    abs(oriented.margin) as favourite_margin,
    case
        when oriented.win_probability >= 0.5 then home.team_name
        else away.team_name
    end as favourite,
    -- How settled the game is, in words, so the headline is a sentence rather
    -- than a number a reader has to calibrate for themselves. The bands are
    -- the ones the model board's calibration curve supports: past about 80%
    -- the model has been reliable, and inside 60% it is close to a coin toss.
    case
        when greatest(oriented.win_probability, 1 - oriented.win_probability) >= 0.8
            then 'a clear favourite'
        when greatest(oriented.win_probability, 1 - oriented.win_probability) >= 0.6
            then 'the better side'
        else 'barely favoured'
    end as verdict
from ${oriented} as oriented
inner join team_season as home
    on oriented.side_id = home.team_id
    and home.season = (select max(season) from team_season)
inner join team_season as away
    on oriented.other_id = away.team_id
    and away.season = (select max(season) from team_season)
where oriented.side_id = (select team_id from ${home_pick})
    and oriented.other_id = (select team_id from ${away_pick})
```

```sql sides
-- Both teams in one result, tagged by side, so the cards and the comparison
-- chart below read from one place and cannot disagree about which team is
-- which.
select
    'home' as side,
    team_id,
    team_name,
    team_logo_url,
    team_color,
    conference_name,
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
    games_vs_top_50
from team_season
where season = (select max(season) from team_season)
    and team_id::varchar = (select team_id from ${home_pick})

union all

select
    'away',
    team_id,
    team_name,
    team_logo_url,
    team_color,
    conference_name,
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
    games_vs_top_50
from team_season
where season = (select max(season) from team_season)
    and team_id::varchar = (select team_id from ${away_pick})
```

{#if matchup.length > 0}

<div class="verdict">
<strong><Value data={matchup} column=favourite /></strong> is
<Value data={matchup} column=verdict />, by
<Value data={matchup} column=favourite_margin fmt='+0.0' /> at a neutral site.
Model win probability: <Value data={matchup} column=favourite_probability fmt='0%' />.
</div>

<div class="sides">
{#each sides as team (team.team_id)}
<div class="side">
<TeamCrest
    teamId={team.team_id}
    name={team.team_name}
    color={team.team_color}
/>
<div class="side-text">
<div class="side-name">{team.team_name}</div>
<div class="side-meta">
{team.conference_name} · {team.record} · rank {team.national_rank}
</div>
</div>
</div>
{/each}
</div>

## What each half of the model says

The prediction is a blend of two ratings that fail differently. Adjusted
efficiency is opponent-adjusted and stable, but it describes a whole season and
barely moves in March. Elo is noisier and not opponent-adjusted beyond who a
team beat, but it is a time series, so it knows a team has won nine straight.

When the two agree, the game is what it looks like. When they disagree, the
blend sits between them and the game is less settled than one number suggests.

<Grid cols=3>
    <BigValue
        data={matchup}
        value=win_probability
        title="The model"
        fmt='0%'
    />
    <BigValue
        data={matchup}
        value=efficiency_probability
        title="Efficiency rating alone"
        fmt='0%'
    />
    <BigValue
        data={matchup}
        value=elo_probability
        title="Elo alone"
        fmt='0%'
    />
</Grid>

Each is the chance the first team wins. The two halves are
<Value data={matchup} column=disagreement fmt='0.0%' /> apart.

<Grid cols=2>
    <BigValue
        data={matchup}
        value=margin
        title="Expected margin, neutral site"
        fmt='+0.0'
    />
    <BigValue
        data={matchup}
        value=margin_at_home
        title="Expected margin, first team at home"
        fmt='+0.0'
    />
</Grid>

Home court is worth 3.5 points in this model, applied to the host only. A
neutral-site game passes zero, which is where the tournament is played and why
that is the number the page leads with.

## The two teams, side by side

```sql comparison
-- Long format, one row per team per measure, which is what lets a grouped bar
-- draw the pair against each other. Each measure is shifted so a longer bar is
-- always the better number, including defence, which is points allowed and so
-- reads backwards otherwise.
select team_name, measure, value
from (
    select
        team_name,
        adjusted_efficiency_margin as "Efficiency margin",
        adjusted_offensive_efficiency - 100 as "Offence above 100",
        100 - adjusted_defensive_efficiency as "Defence below 100",
        adjusted_tempo - 60 as "Tempo above 60"
    from ${sides}
)
unpivot (
    value for measure in (
        "Efficiency margin", "Offence above 100",
        "Defence below 100", "Tempo above 60"
    )
)
```

<BarChart
    data={comparison}
    x=measure
    y=value
    series=team_name
    type=grouped
    swapXY=true
    yFmt='+0.0'
    title="Every measure, shifted so a longer bar is better"
/>

```sql ranks
-- The same comparison as ranks rather than ratings. A rating says how good a
-- team is; a rank says how many teams are better, which is the version a
-- reader can hold in their head.
select
    team_name,
    measure,
    rank_value
from (
    select
        team_name,
        national_rank as "Overall",
        offense_rank as "Offence",
        defense_rank as "Defence",
        schedule_strength_rank as "Schedule faced"
    from ${sides}
)
unpivot (
    rank_value for measure in ("Overall", "Offence", "Defence", "Schedule faced")
)
```

<DataTable data={ranks} groupBy=measure groupType=section>
    <Column id=team_name title="Team" />
    <Column id=rank_value title="National rank" fmt='0' align=right />
</DataTable>

## The rest of the field

```sql gauntlet
-- The first team against everyone the model rates in the top 25, at a neutral
-- site, so nothing separates these games except how good it thinks the two
-- sides are.
select
    other.national_rank as opponent_rank,
    other.team_name as opponent,
    other.conference_name as conference,
    other.record as opponent_record,
    oriented.margin,
    oriented.win_probability,
    oriented.efficiency_probability,
    oriented.elo_probability,
    abs(oriented.efficiency_probability - oriented.elo_probability) as disagreement
from ${oriented} as oriented
inner join team_season as other
    on oriented.other_id = other.team_id
    and other.season = (select max(season) from team_season)
where oriented.side_id = (select team_id from ${home_pick})
    and other.national_rank <= 25
order by other.national_rank
```

<DataTable data={gauntlet} rows=15 search=true>
    <Column id=opponent_rank title="#" fmt='0' align=right />
    <Column id=opponent title="Opponent" />
    <Column id=conference title="Conference" />
    <Column id=opponent_record title="Record" align=right />
    <Column id=margin title="Margin" fmt='+0.0' align=right />
    <Column id=win_probability title="Model" fmt='0%' align=right
        contentType=colorscale colorScale=primary />
    <Column id=efficiency_probability title="Efficiency only" fmt='0%' align=right />
    <Column id=elo_probability title="Elo only" fmt='0%' align=right />
    <Column id=disagreement title="Gap" fmt='0%' align=right />
</DataTable>

{:else}

<Alert status="info">

**No price for this pairing.** The matchup grid is built from teams with a
settled rating in the current season, so a team that has not played enough to
be rated is not in it yet. Pick another opponent, or come back after the next
nightly run.

</Alert>

{/if}

The same view without the pickers, fixed on one featured game, is on the
[matchup board](https://lab.cameronspilker.com/charts/matchup/). Both read the same
`mart_matchup_odds` table, so they cannot disagree about a price.

<style>
    .pickers {
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
        align-items: flex-end;
        margin-bottom: 1.5rem;
    }

    /* Derived from `currentColor` so the card follows the reader's appearance
       without naming a hex twice, the same rule the other components keep. */
    .verdict {
        margin: 1.5rem 0 1rem;
        padding: 1rem 1.25rem;
        border: 1px solid color-mix(in srgb, currentColor 18%, transparent);
        border-radius: 0.375rem;
        background: color-mix(in srgb, currentColor 4%, transparent);
        font-size: 1.05rem;
        line-height: 1.5;
    }

    .sides {
        display: flex;
        flex-wrap: wrap;
        gap: 1.5rem;
        margin-bottom: 2rem;
    }

    .side {
        display: flex;
        gap: 0.75rem;
        align-items: center;
        min-width: 15rem;
    }

    .side-name {
        font-weight: 600;
        line-height: 1.3;
    }

    .side-meta {
        font-size: 0.8rem;
        opacity: 0.7;
        line-height: 1.4;
    }
</style>
