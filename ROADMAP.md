# Roadmap

Where this repo stands and what comes next. Grouped by what unblocks what,
not by calendar week — the ordering matters more than the dates.

## Done

- Ingestion for GitHub and PyPI, with rate limiting, retries, and error isolation
- Parquet landing zone and idempotent DuckDB loads
- dbt project: staging → intermediate → marts, 87 passing checks
- Semantic models and metrics defined in code
- Dagster asset graph (16 assets), jobs, schedules, and an ingestion sensor
- Evidence dashboard with four pages, every query verified against the warehouse
- CI on every PR; weekly pipeline workflow written

## Next — in order

### 1. Run the pipeline against the real APIs (blocks everything below)

Everything currently runs on synthetic data from `ingest demo`. Nothing here is
a real finding about the ecosystem until this is done.

- [ ] Create a GitHub token with **no scopes** (public data only), store it as
      the `INGEST_GITHUB_TOKEN` Actions secret
- [ ] Run `ingest all` locally and confirm both extractors succeed against live
      endpoints — the GitHub `subscribers_count` and the pypistats response
      shape are the two most likely places reality differs from the fixtures
- [ ] Run `dbt build` on the real extract. Expect the custom star-collapse test
      to be the first thing that catches a genuine data problem
- [ ] Remove `data/warehouse.duckdb` from `.gitignore` once the committed file
      holds real data, and delete the synthetic-data warning banner from
      `dashboard/pages/index.md`

### 2. Accumulate history

GitHub reports state, not history, so the star series has exactly as many
points as the pipeline has runs. The dashboard is thin until this compounds.

- [ ] Enable the weekly workflow and let it run for several weeks
- [ ] Consider seeding backfill from a public archive (GH Archive, or the
      Software Heritage dataset) if a longer series is worth the ingestion work
- [ ] Revisit `mart_tool_comparison`'s trailing averages once there are more
      than a handful of weeks — the window is currently "all observed weeks"

### 3. Deploy the dashboard

- [ ] Deploy `dashboard/` to Vercel, root directory `dashboard`, build command
      `npm run sources && npm run build`
- [ ] Confirm the DuckDB file resolves at build time from the repo checkout
- [ ] Point a subdomain at it and link it from cameronspilker.com
- [ ] Verify it renders inside an iframe, since the portfolio site embeds it

### 4. Host the dbt docs

- [ ] Add a workflow step publishing `transform/target/` to GitHub Pages
- [ ] Link the docs from both the dashboard nav and the portfolio site
- [ ] Fill in the model and column descriptions that are still thin — the docs
      site is a portfolio artifact, and empty descriptions show

### 5. Harden

- [ ] Add dbt source freshness to CI (`dbt source freshness`) so a silently
      failing extractor fails a build instead of quietly serving stale marts
- [ ] Add Dagster asset checks mirroring the dbt tests, so a failure surfaces
      in the orchestrator UI rather than only in dbt logs
- [ ] Make ingestion incremental — currently every run rewrites the snapshot;
      fine at 17 tools, not fine at 200
- [ ] Add a `dbt build --select state:modified+` slim-CI path once the model
      count justifies it

### 6. Deepen the analysis

The pipeline is the point, but the findings are what make it worth reading.

- [ ] Add issue and PR data: time-to-first-response and time-to-close are much
      stronger health signals than open-issue counts
- [ ] Add a written "what the data says" page — the ecosystem story, not just
      the charts. This is the piece a hiring manager actually reads
- [ ] Expand `tools.yml` beyond 17 tools once ingestion is incremental

## Known limitations

- **Contributor counts cap at 500.** GitHub's paginated list stops there. The
  `is_count_capped` flag carries this to the dashboard rather than hiding it,
  but the numbers for large repos are floors.
- **Stars are a weak proxy for adoption.** They measure attention. Downloads
  are closer to usage, and only exist for tools that ship a Python package.
- **No history before first run.** See step 2.
