---
title: How it works
---

<script>
    import ViewNav from '$lib/ViewNav.svelte';
</script>

<ViewNav current="how-it-works" />

One repository builds everything here, from the API call to this page.
[Source on GitHub](https://github.com/CameronSpilker/full-data-stack-lab)
· [dbt docs and lineage](https://lab.cameronspilker.com/docs/)

## The pipeline

1. **Ingest** (Python, httpx). Games, box scores, betting lines and adjusted
   efficiency from `collegebasketballdata.com`, landed as dated Parquet so a run
   can be replayed from disk.
2. **Store** (DuckDB). One warehouse file with key-based upserts, read by dbt
   and both dashboards.
3. **Transform** (dbt Core). Staging, intermediate and marts, with the predictor
   defined once in a macro so every page prices a game the same way.
4. **Orchestrate** (Dagster). An asset graph that rebuilds the models when fresh
   scores land.
5. **Present** (Evidence and dbt Charts). Dashboards as code, in the same repo
   as the models they read.

## When it runs

The cron expressions from `orchestration/full_data_stack_lab/jobs.py`, in
Mountain time.

| Schedule | Cron | What it rebuilds |
| --- | --- | --- |
| `nightly_in_season_schedule` | `0 6 * * *` | The season in progress, then the dbt graph |
| `march_madness_schedule` | `0 7,19 * 3 *` | Everything, twice a day through March |
| `team_dimension_schedule` | `0 5 1 * *` | The team list and conference membership |

GitHub Actions runs the same pipeline daily and publishes the warehouse as a
release asset, which is what this site builds from.

## The pages

- [Overview](/): the top 25, offense against defense, and the biggest upsets,
  for any season.
- [Rankings](/rankings): the whole field in tiers, for any season.
- [Teams](/scorecard): one team in one season, compared against any others.
- [Matchup](/matchup): any two teams priced at a neutral site.
- [Conferences](/conferences): leagues ranked on their median team.
- [Picks](/picks): upcoming games where the model disagrees with the market.
- [March Madness](/march-madness): the projected field and its simulated odds.
- [Model](/model): accuracy and calibration, real forecasts kept apart from
  hindsight.
