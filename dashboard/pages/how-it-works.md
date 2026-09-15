---
title: How it works
---

<script>
    import ViewNav from '$lib/ViewNav.svelte';
</script>

<ViewNav />

Everything on this site is built by one repository, from the API call to the
page you are reading. This is what each stage does and why it is the way it is.

[Read the source on GitHub](https://github.com/CameronSpilker/full-data-stack-lab)
· [Browse the dbt docs and lineage](https://lab.cameronspilker.com/docs/)
· [The same marts, in dbt Charts](https://lab.cameronspilker.com/charts/)

## The pipeline, in order

### 1. Ingest, with Python and httpx

`collegebasketballdata.com` for games, box scores, betting lines, and adjusted
efficiency. Every extract lands as dated Parquet before anything reads it, so a
run is replayable from disk without touching the API again.

### 2. Store, with DuckDB

A Parquet landing zone and key-based upserts into a single warehouse file that
both dbt and this dashboard read. A rolling window corrects what it covers and
leaves the rest of history alone.

### 3. Transform, with dbt Core

Staging, intermediate, marts. 25 models behind 139 tests, with the predictor
defined once in a macro so every consumer prices a game the same way.

### 4. Orchestrate, with Dagster

An asset graph rather than a task graph, so ingestion and the dbt DAG share one
lineage view. A sensor watching the games asset rebuilds the models the moment
fresh scores land, which means this dashboard is never more than one run behind
the warehouse.

### 5. Present, with Evidence

Dashboards as code, versioned in the same repository as the models they read.
Nothing here lives only inside a BI tool's UI.

### 6. And with dbt Charts, on /charts

The same marts, read a second way. A [dbt Charts](https://dbtcharts.com) board
is one YAML file: its queries, its charts and its layout, with no component
code. The pipeline renders the boards to static pages against the warehouse it
has just built and tested, and publishes them beside the docs, so
[/charts](https://lab.cameronspilker.com/charts/) is drawn from exactly the
run that produced these pages.

Two presentation layers over one set of marts is the point rather than an
accident. Evidence gets the interactive pages, where a reader picks a team and
the page answers. dbt Charts gets the ones that are the same for everybody,
where the whole board is a file small enough to read in a pull request.

## When it runs

These are the literal cron expressions from the Dagster definitions in
`orchestration/full_data_stack_lab/jobs.py`, all evaluated in Mountain time.

| Schedule | Cadence | Cron | What it rebuilds |
| --- | --- | --- | --- |
| `nightly_in_season_schedule` | Daily, 06:00 | `0 6 * * *` | Scores, box scores, betting lines and ratings for the season in progress, then the dbt graph behind them |
| `march_madness_schedule` | Twice daily through March | `0 7,19 * 3 *` | The whole graph, every extractor followed by every model |
| `team_dimension_schedule` | Monthly, the 1st | `0 5 1 * *` | The team list and conference membership |

Games finish late, so 06:00 Mountain is after the last west coast final and
before anyone looks at the dashboard. March gets a second session because the
odds move between afternoon and evening. Conference realignment is an offseason
event, so refreshing the team list nightly would spend API budget rewriting rows
that cannot change.

GitHub Actions runs the same pipeline daily and publishes the rebuilt warehouse
as a release asset, so this dashboard builds from a clean checkout without a
local run.

## What is on the rest of the site

- [Season overview](/): every Division I team ranked on adjusted efficiency
  margin, with tempo, record and strength of schedule alongside it.
- [Tournament odds](/bracket): the projected 64-team field and the odds of every
  team reaching each round, from 20,000 simulated brackets.
- [Conferences](/conferences): ranked on the median team's rating rather than
  the best one, because one outstanding program can carry a mediocre league's
  reputation.
- [Team scorecard](/scorecard): one team on one page, defaulting to BYU. The
  short version at the top, then the working: where they rank, how the season
  has moved, the wins that count, and what the simulations make of their March.
- [Rankings](/rankings): the whole field in one order, cut into tiers, and
  every team plotted offence against defence.
- [Matchup](/matchup): any two teams priced at a neutral site, with each half
  of the model shown separately so their disagreement is readable.
- [Upcoming picks](/picks): what the model makes of the games that have not
  been played yet, rebuilt every morning. Ranked on where it disagrees with the
  betting market rather than on how confident it is, because a 95% favourite is
  95% on every screen in the country.
- [How good is the model?](/model): accuracy, log loss, Brier score and
  calibration curves for each predictor, with real forecasts kept separate from
  the ones that saw the future.
- Team pages: a game log, an Elo timeline, and the priced matchup against
  anyone else in the country. Open one from any team on the season overview.
- [The dbt Charts boards](https://lab.cameronspilker.com/charts/): seven static
  boards drawn straight from the marts. No team picker and no filters: a board
  is the same page for everybody, which is what lets it be one YAML file. The
  two that are about one team or one game, the scorecard and the matchup, pick
  their subject in SQL and link back here for the version that lets you
  choose.
