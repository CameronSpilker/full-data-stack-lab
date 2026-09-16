# Boards

[dbt Charts](https://dbtcharts.com) boards, served at
[lab.cameronspilker.com/charts](https://lab.cameronspilker.com/charts/).

A board is one YAML file holding its own queries, charts and layout. There is no
component code and no separate query directory: the SQL that feeds a chart sits
a few lines above it in the same file, so a column rename and the chart that
reads it are one diff.

| File | Page | What it answers |
| --- | --- | --- |
| `index.yml` | `/charts/` | Headline numbers and the way into the other six |
| `rankings.yml` | `/charts/rankings/` | The whole field in rating order, tiered, and plotted offence against defence |
| `scorecard.yml` | `/charts/scorecard/` | One team on one screen: rank, strengths, and which way the season is going |
| `matchup.yml` | `/charts/matchup/` | One game priced at a neutral site, with each half of the model shown separately |
| `model.yml` | `/charts/model/` | Which predictor was best, and whether its confidence means anything |
| `season.yml` | `/charts/season/` | Who was good and which conferences were deep |
| `tournament.yml` | `/charts/tournament/` | Title odds, seed value and survival, from 20,000 simulated brackets |

Every board opens with the same top bar: eight buttons in a fixed order, seven
for the boards and one for the Evidence dashboard, with the button for the page
you are on filled in rather than linked. A button is a nested block carrying a
link, styled through the two anchors each file defines once, `&nav_button` and
`&nav_current`, so the buttons on a page cannot drift apart from each other.

Under the buttons, inside the same card, is one line saying what the page you
landed on gets you. That line is the board's description, and the card is the
only place it appears: clicking a button is how you read it, so there is no
list of all seven descriptions anywhere for the boards to drift away from.

The bar itself is copied into all seven files, because a board cannot inherit a
layout row from `meta.yml`. Adding a board means adding a row to the table above
and a button to all seven bars, in the same order in each. `scripts/render-charts.sh`
renders every board, so a bar that was missed is visible in the output rather
than silently wrong.

Markdown bold does not render in the serif face these pages draw with, so a
button label is plain text and the current page is marked by the fill alone.

Two of the boards have a counterpart on the Evidence side that does the same
job with a picker on it: `/scorecard` and `/matchup`. They are not duplicates
by accident. These pages render to static HTML, which is what makes them cheap
and what means a variable widget cannot survive the export, so a board is fixed
on one team or one game and says so with a link to the version that is not.
Both read the same marts, so the two can differ in what they let you ask and
never in the answer.

`meta.yml` is not a board. dbt Charts applies it to every file in this folder,
and it carries the two things that must not be decided per board: the palette,
ported stop for stop from `dashboard/evidence.config.yaml` so a reader moving
between the two presentation layers sees the same three category hues, and
`title.font.case: none`, because the default is Chicago title case and the rest
of the site is sentence case.

Boards read `marts` only, the same boundary the Evidence dashboard keeps. A
question the marts cannot answer is a question for a new dbt model, not for a
longer query here.

## Working on one

```bash
pip install -r charts/requirements.txt

# The boards need a warehouse. Either build one from synthetic seasons:
pip install -e ingestion -r transform/requirements.txt
ingest demo
(cd transform && dbt deps && DUCKDB_PATH=../data/warehouse.duckdb dbt build --target ci)

# ...or fetch the real one the pipeline published:
curl -fsSL -o data/warehouse.duckdb \
  https://github.com/CameronSpilker/full-data-stack-lab/releases/download/warehouse-latest/warehouse.duckdb
```

Then, from the repository root:

```bash
dct validate charts/*.yml   # schema and cross-references, no database needed
dct serve                   # live preview on localhost, with the filters live
bash scripts/render-charts.sh   # exactly what CI and the pipeline produce
```

`dct docs` is the full YAML reference offline, and `dct docs <topic>` is one
section of it. Unknown keys are errors rather than warnings, so `dct validate`
catches most mistakes before anything touches the warehouse.

## How a board reaches the site

The pages are static. `scripts/render-charts.sh` runs each board's SQL against
the warehouse and writes the drawn result to HTML, the daily pipeline publishes
that as `charts.tar.gz` on the `warehouse-latest` release, and the dashboard
build unpacks it into `dashboard/static/charts`. It is the same route the dbt
docs take.

Two consequences worth knowing:

- A board is only as fresh as the last pipeline run, exactly like every number
  on the Evidence pages.
- Editing a board and pushing to `main` re-runs the pipeline, because
  `charts/**` is in its trigger paths. A Vercel rebuild on its own would only
  re-fetch the pages the last pipeline run drew.

Static also means the variable widgets `dct serve` gives you do not survive the
render, so the boards here are authored without them. A board that is about one
team or one game picks its subject in SQL instead: `scorecard.yml` and
`matchup.yml` both open with a `focus` CTE that resolves to BYU, or to the
top-ranked team when a season arrives without them, which is also what makes
them render against the synthetic demo seasons. A page that needs the reader to
choose belongs on the Evidence side, and both of those boards link to it.
