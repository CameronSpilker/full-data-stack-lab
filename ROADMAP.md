# Roadmap

Where this repo stands and what comes next. Grouped by what unblocks what,
not by calendar week — the ordering matters more than the dates.

## Done

- Ingestion for collegebasketballdata.com (teams, games, box scores, betting
  lines) and Barttorvik T-Rank, with retries, rate limiting, and error isolation
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

### 1. Run the pipeline against the real APIs (blocks everything below)

Everything currently runs on simulated seasons from `ingest demo`. Nothing here
is a real finding about college basketball until this is done.

- [ ] Register at [collegebasketballdata.com](https://collegebasketballdata.com)
      for a free API key, store it as the `CBD_API_KEY` Actions secret
- [ ] Run `ingest preflight --season 2026` first. It calls every live source
      against a single season, writes nothing, and reports what share of each
      column actually came back — so a parser reading the wrong key shows up as
      `adj_oe 0.0% FAIL` rather than as a quietly empty column three layers
      downstream. It exits non-zero until every critical field is populated
- [ ] Then run `ingest all --season 2026` — one season, not five. The two
      places reality is most likely to differ from the fixtures:
      - **Barttorvik's CSV layout.** `torvik.py` reads it by header when one is
        present and positionally when it is not. The positional map in
        `POSITIONAL_COLUMNS` was written without a live response to check
        against, and is the single most likely thing in this repo to be wrong.
        The parser refuses to load a result where adjusted efficiency did not
        come through, so a failure will be loud rather than silent.
      - **CBD's exact field names.** `_first()` accepts several spellings per
        field, but a field named something not in that list arrives as null.
- [ ] Run `dbt build` on the real extract. Expect
      `assert_every_rating_matches_a_team` to be the first thing that fails —
      it names every Barttorvik school that did not join to a team, and those
      names go into `seeds/team_name_crosswalk.csv`. That is the intended
      workflow, not a defect
- [ ] Sanity-check the numbers against a public source: the top 25 by adjusted
      efficiency margin should look broadly like KenPom's or Barttorvik's own
      top 25. If it does not, the join is wrong somewhere
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
- [ ] Backfill point-in-time ratings from Barttorvik's date-filtered endpoints
      if they can be made to work, which would remove the wait entirely

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

- [ ] Deploy `dashboard/` to Vercel, root directory `dashboard`, build command
      `npm run sources && npm run build`
- [ ] Confirm the DuckDB file resolves at build time from the repo checkout
- [ ] Point a subdomain at it and link it from cameronspilker.com
- [ ] Verify it renders inside an iframe, since the portfolio site embeds it

### 5. Host the dbt docs

- [ ] Add a workflow step publishing `transform/target/` to GitHub Pages
- [ ] Link the docs from both the dashboard nav and the portfolio site

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
- **Ratings are season-to-date, not as-of-date.** Barttorvik publishes current
  state, so history exists only from the first pipeline run forward.
- **No player-level data.** Team ratings cannot see that a starter is out.
