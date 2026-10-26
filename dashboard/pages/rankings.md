---
title: Rankings
---

<script>
    import ViewNav from '$lib/ViewNav.svelte';
    import TeamCrest from '$lib/TeamCrest.svelte';
</script>

<ViewNav current="rankings" />

The whole field in one order, for any season.

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

<Dropdown
    data={seasons}
    name=season
    value=season
    label=season_label
    title="Season"
    defaultValue={seasons[0]?.season}
/>

```sql field
-- The tiers are cut on national rank rather than on an efficiency number.
-- Cutting on margin reads better, because the bands are the diagonals a reader
-- already sees on the quadrant below, but it hard-codes the spread of one
-- season's ratings and the synthetic demo seasons are far narrower than a real
-- one. A rank cut is the same diagonal, drawn where the field actually sits.
--
-- Keep this cut in step with charts/rankings.yml in the repository.
select
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
    made_ncaa_tournament,
    case
        when national_rank <= 16 then 'Title favourites'
        when national_rank <= 48 then 'Final four potential'
        when national_rank <= 100 then 'Hit or miss'
        else 'The rest'
    end as tier
from team_season
where season = (select season from ${season_pick})
order by national_rank
```

```sql headline
select
    count(*) as teams,
    max(adjusted_efficiency_margin) as best_margin,
    count(*) filter (where national_rank <= 16) as favourites,
    count(distinct conference_name) as conferences
from ${field}
```

<Grid cols=3>
    <BigValue data={headline} value=teams title="Teams ranked" fmt='0' />
    <BigValue data={headline} value=best_margin title="Best rating in the field" fmt='+0.0' />
    <BigValue data={headline} value=conferences title="Conferences represented" fmt='0' />
</Grid>

Ranked on adjusted efficiency margin: points per 100 possessions better than an
average team, adjusted for opponent.

## The top of the order

```sql top_25
select
    team_id,
    national_rank,
    team_name,
    team_logo_url,
    team_color,
    conference_name,
    record,
    tier,
    adjusted_efficiency_margin,
    offense_rank,
    defense_rank
from ${field}
where national_rank <= 25
order by national_rank
```

<div class="ladder">
{#each top_25 as team (team.team_id)}
<a class="rung" href="/teams/{team.team_id}">
<span class="rung-rank">{team.national_rank}</span>
<TeamCrest
    teamId={team.team_id}
    name={team.team_name}
    color={team.team_color}
    size={32}
/>
<span class="rung-name">{team.team_name}</span>
<span class="rung-meta">{team.conference_name} · {team.record}</span>
<span class="rung-rating">{team.adjusted_efficiency_margin > 0 ? '+' : ''}{team.adjusted_efficiency_margin.toFixed(1)}</span>
</a>
{/each}
</div>

## Offence against defence

<LogoScatter
    data={field}
    x=adjusted_offensive_efficiency
    y=adjusted_defensive_efficiency
    series=tier
    yMin=86
    yMax=128
    xMin=84
    xMax=136
    yAxisTitle="Points allowed per 100 possessions"
    xAxisTitle="Points scored per 100 possessions"
    title="Every team in the country"
    subtitle="Up and to the right is good at both ends. The axes are fixed, so a position means the same in every season."
    tooltipTitle=team_name
/>

## What each tier looks like

```sql tiers
select
    tier,
    count(*) as teams,
    min(national_rank) as best_rank,
    max(national_rank) as worst_rank,
    avg(adjusted_efficiency_margin) as avg_margin,
    avg(adjusted_offensive_efficiency) as avg_offense,
    avg(adjusted_defensive_efficiency) as avg_defense,
    count(*) filter (where made_ncaa_tournament) as made_the_field
from ${field}
group by tier
order by avg_margin desc
```

<DataTable data={tiers}>
    <Column id=tier title="Tier" />
    <Column id=teams title="Teams" fmt='0' align=right />
    <Column id=best_rank title="From" fmt='0' align=right />
    <Column id=worst_rank title="To" fmt='0' align=right />
    <Column id=avg_margin title="Avg margin" fmt='+0.0' align=right />
    <Column id=avg_offense title="Avg offence" fmt='0.0' align=right />
    <Column id=avg_defense title="Avg defence" fmt='0.0' align=right />
    <Column id=made_the_field title="Made the field" fmt='0' align=right />
</DataTable>

## The full field

Sortable and searchable. Each row opens that team's page.

```sql field_linked
-- The same rows with a link column, so a row in the table opens that team's
-- page. Built here rather than in the mart: it is a fact about this site's
-- routes, not about the season. `/teams/<id>` is the route every other
-- table on the site links to, and it is a real prerendered page per team
-- rather than a query string the dropdown may or may not read.
select *, '/teams/' || team_id as team_link
from ${field}
```

<DataTable data={field_linked} rows=25 search=true link=team_link>
    <Column id=national_rank title="#" fmt='0' align=right />
    <Column id=team_name title="Team" />
    <Column id=conference_name title="Conference" />
    <Column id=tier title="Tier" />
    <Column id=record title="Record" align=right />
    <Column id=adjusted_efficiency_margin title="Margin" fmt='+0.0' align=right
        contentType=colorscale colorScale=primary />
    <Column id=adjusted_offensive_efficiency title="Offence" fmt='0.0' align=right />
    <Column id=offense_rank title="Off rank" fmt='0' align=right />
    <Column id=adjusted_defensive_efficiency title="Defence" fmt='0.0' align=right />
    <Column id=defense_rank title="Def rank" fmt='0' align=right />
    <Column id=adjusted_tempo title="Tempo" fmt='0.0' align=right />
    <Column id=elo_rating title="Elo" fmt='0' align=right />
</DataTable>

<style>
    .ladder {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        margin: 1.5rem 0;
    }

    /* Colours derived from `currentColor` so the rows follow the reader's
       appearance without naming a hex twice. */
    .rung {
        display: grid;
        grid-template-columns: 2.5rem auto 1fr auto auto;
        gap: 0.75rem;
        align-items: center;
        padding: 0.4rem 0.6rem;
        border: 1px solid color-mix(in srgb, currentColor 12%, transparent);
        border-radius: 0.375rem;
        text-decoration: none;
        color: inherit;
    }

    .rung:hover {
        border-color: color-mix(in srgb, currentColor 32%, transparent);
        background: color-mix(in srgb, currentColor 5%, transparent);
    }

    .rung-rank {
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 0.85rem;
        text-align: right;
        opacity: 0.6;
    }

    .rung-name {
        font-weight: 600;
        font-size: 0.9rem;
    }

    .rung-meta {
        font-size: 0.78rem;
        opacity: 0.65;
        text-align: right;
    }

    .rung-rating {
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 0.85rem;
        min-width: 3.5rem;
        text-align: right;
    }

    /* The ladder is a grid at reading widths and a simpler stack on a phone,
       where five columns of it collapse into something unreadable. */
    @media (max-width: 40rem) {
        .rung {
            grid-template-columns: 2rem auto 1fr auto;
        }

        .rung-meta {
            display: none;
        }
    }
</style>
