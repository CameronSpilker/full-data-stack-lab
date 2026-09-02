# Roadmap

Where this repo stands and what comes next. Grouped by what unblocks what,
not by calendar week — the ordering matters more than the dates.

## Done

- Ingestion for collegebasketballdata.com (teams, games, box scores, betting
  lines, adjusted efficiency), with retries, rate limiting, error isolation,
  and date-window paging around the API's undocumented 3,000 record limit
- Parquet landing zone and idempotent, partition-aware DuckDB loads
- dbt project: staging → intermediate → marts: 22 models, 113 passing tests
- Elo computed sequentially as a dbt Python model
- Strength of schedule solved iteratively in SQL, as an independent control on
  the published ratings
- A predictor defined once in a macro, so every consumer prices a game the same
- Backtest with proper scoring rules, calibration curves, and a leakage flag
  separating real forecasts from models that saw the future
- Monte Carlo tournament simulation, 20,000 brackets
- Projected 64-team field derived from conference champions and at-large ratings
- Evidence dashboard: season overview, bracket odds, team pages, conferences,
  and a page reporting the model's own accuracy
- Dagster asset graph, jobs, schedules, and an ingestion sensor
- CI on every PR; daily pipeline workflow written

## Next — in order

### 1. Run the pipeline against the real APIs

The first live preflight found three things, all now fixed. Kept here because
the reasoning matters more than the checkboxes.

- [x] Register for a free API key and store it as the `CBD_API_KEY` secret
- [x] Run `ingest preflight --season 2026`. It found that the games feed
      stopped on 2026-01-06, the box score parser returned nothing from 3,000
      records, and Barttorvik returned 403
- [x] **The 3,000 record limit.** A season-wide request returns well-formed
      JSON that simply stops in January, losing the back half of the season
      including the tournament. Games and lines are now read in date windows
      that split and retry when one comes back at the limit
- [x] **The box score shape.** Each `/games/teams` record is one team's line
      with nested stat objects, not a game with a `teams` array. The parser was
      written against a fixture that invented the second shape and returned
      zero rows from real data. The fixture is now copied from a live response
- [x] **Barttorvik is unreachable from CI.** Its CDN returns 403 to any request
      from a data centre, under any User-Agent, so no scheduled pipeline could
      ever read it. Ratings now come from CBD's own `/ratings/adjusted`, keyed
      on the same team id as every other table, which removed the name
      crosswalk, its seed, and the build failure that maintained it
- [x] Run the pipeline against the live APIs. It loaded 6,067 games, 12,082
      box score lines, 10,277 betting lines, and 365 rated teams, then failed
      `assert_scores_are_plausible` on 18 games. All 18 were 0-0: cancelled
      fixtures that the extractor had promoted to completed because both
      scores were present, 0 being a score. Fixed in the parser and again in
      staging, since raw already held the bad rows
- [ ] Sanity-check the numbers against a public source: the top 25 by adjusted efficiency margin should look
      broadly like KenPom's. If it does not, something upstream is wrong
- [ ] Remove `data/warehouse.duckdb` from `.gitignore` once the committed file
      holds real data, and delete the synthetic-data banner from
      `dashboard/pages/index.md`

### 2. Make the blended model honest

The full model currently cannot be backtested, because the only efficiency
ratings available describe the whole season. This is the most valuable
modelling work left.

- [ ] Let the daily pipeline run through a season so `raw.ncaa_ratings`
      accumulates a snapshot per day
- [ ] Change `int_game_predictions` to join the rating snapshot as of the day
      *before* each game rather than the latest one
- [ ] Re-score. Expect the blended model to get worse and become meaningful
- [ ] Look for a date-filtered ratings endpoint that would backfill
      point-in-time ratings and remove the wait entirely

### 3. Use the real bracket in March

- [ ] Add an extractor for the official field — [ncaa-api](https://github.com/henrygd/ncaa-api)
      wraps ncaa.com's own endpoints and is the authoritative source for seeds,
      regions, and matchups. Self-host it; the public instance is rate limited
- [ ] Have `mart_bracket` prefer the official field when one exists and fall
      back to the projection before Selection Sunday
- [ ] Add the First Four. Currently the field is 64, not 68 — the play-in games
      are omitted, which is defensible for probabilities and wrong for a bracket
      someone wants to fill in
- [ ] Score the projected field against the real one: how many teams did the
      bracketology get right, and how close were the seeds?

### 4. Deploy the dashboard

The workflow is written: `.github/workflows/publish.yml` builds the Evidence
site and the dbt docs from the committed warehouse and deploys both to GitHub
Pages, refusing to publish if the warehouse is missing. See the Deployment
section of the README. What is left is the switching on, and all of it depends
on step 1.

- [x] Build and deploy the dashboard from CI, with no deploy credentials
- [ ] Set Settings > Pages > Source to GitHub Actions
- [ ] Run the publish workflow once the pipeline has committed a real warehouse
- [ ] Confirm the DuckDB file resolves at build time from the repo checkout
- [ ] Set `lab.dashboard` in the portfolio repo's `src/content/site.ts`, which
      is the one line that lights up the link there
- [ ] Point a subdomain at it, and set `basePath` back to `""` when you do
- [ ] Verify it renders inside an iframe, in case the portfolio site embeds it

### 5. Host the dbt docs

- [x] Add a workflow step publishing `transform/target/` to GitHub Pages. The
      publish workflow puts it at `/docs`, beside the dashboard
- [ ] Link the docs from the dashboard nav
- [ ] Set `lab.docs` in the portfolio repo's `src/content/site.ts`

### 6. Harden

- [ ] Add `dbt source freshness` to CI so a silently failing extractor fails a
      build instead of quietly serving stale marts
- [ ] Add Dagster asset checks mirroring the dbt tests, so a failure surfaces in
      the orchestrator UI rather than only in dbt logs
- [ ] Make game ingestion incremental — the current run replaces the whole
      season nightly, which is fine at 5,500 games and wasteful at five seasons
- [ ] Add a `dbt build --select state:modified+` slim-CI path

### 7. Deepen the model

The pipeline is the point, but the predictions are what make it worth reading.

- [ ] **Beat the closing line, or find out you cannot.** The market is loaded
      and scored already; add an explicit against-the-spread record and a
      hypothetical bankroll to `mart_model_accuracy`. Expect to lose to it —
      that is the honest and interesting result
- [ ] Tune the blend weights against the backtest rather than setting them by
      hand in `dbt_project.yml`. A small grid search would do it
- [ ] Add injury and availability data. It is the largest single input the
      model is missing, and the reason a rating can be badly wrong in March
- [ ] Add possession-level four factors from the box scores to the prediction,
      rather than only the season-level ones from the ratings feed
- [ ] Consider hoopR's prebuilt Parquet releases for deep history — schedules
      and box scores back to 2002, no API budget, which would take the backtest
      from five seasons to twenty
- [ ] Add a written "what the data says" page. This is the piece a hiring
      manager actually reads

## Known limitations

- **The blended model cannot yet be backtested honestly.** See step 2. It is
  flagged everywhere it appears rather than quietly presented as a forecast.
- **The field is 64, not 68.** See step 3.
- **Conference tournaments are close to coin flips.** A build warning reports
  the slices where a point-in-time model does no better than guessing, and this
  is usually the one that shows up. It is a finding, not a defect: teams from
  the same league at neutral sites strip out most of what a rating knows.
- **Ratings are season-to-date, not as-of-date.** The feed publishes current
  state, so history exists only from the first pipeline run forward.
- **No player-level data.** Team ratings cannot see that a starter is out.
