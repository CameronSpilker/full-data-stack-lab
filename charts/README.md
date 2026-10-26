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
| `tournament.yml` | `/charts/tournament/` | March Madness: title odds, seed value and survival, from 20,000 simulated brackets |

Every board opens with the same header: a navy court banner with the season
it reports on and seven buttons in a fixed order, one per board, with the
button for the page you are on filled in orange rather than linked. The
boards are a site of their own under `/charts`, so the bar never links to the
Evidence dashboard.

The banner is a custom chart drawn by `templates/court_banner.svg.j2`, and the
list of boards lives in that template, so adding a board means adding a row
to the table above and one line to the template. Each board extends
`_header.yml` for the query the banner reads, and still declares
`charts.banner` itself (type, template, query, height and which button it is
on), because dbt Charts checks that a chart is complete before it merges in
what a board extends. Under the banner is one line saying what the page gets
you.

Home, Rankings, Scorecard and Season have a season picker, and Scorecard and
Matchup have team pickers. On the published site every board is served live,
so the pickers work there as they do under `dct serve` (see below).

`meta.yml` is not a board. dbt Charts applies it to every file in this folder,
and it carries what must not be decided per board: the look (a pale maple
floor, white cards, navy ink, and Oswald for headings and numbers the way a
scoreboard sets them), the palette (one blue, its ramp, a grey, and a red for the
bad side of a baseline), and
`title.font.case: none`, because the default is Chicago title case and the
rest of the site is sentence case. Files starting with an underscore, like
`_header.yml`, are pieces boards extend and are never rendered as pages.

## Colour

Colour says what kind of number it is, the same way on every board, so a
reader learns it once:

| Kind of number | Colour | Examples |
| --- | --- | --- |
| Which team, and nothing else | The team's own colours | Bars in a top-N list (Home, Season, title odds), both teams in a matchup, the rings on the season scatter |
| Any other number: a rating, a chance, simulation output | Blue | Elo lines, margin columns, seed value, the survival grid, win probability columns |
| Groups that need telling apart | One blue at three depths, darkest first | The ranking tiers (which also draw larger the higher they are), the three models |
| Signed around a baseline (zero, the median) | Blue for the good side, red for the bad side, grey for the middle | Conference depth, a team's strengths by thirds, game margins |
| Context, not a contender | Grey | "The rest", the model that saw its own season, the calibration diagonal |

There is one hue for data, so no reader has to ask what an orange bar means.
Orange belongs to the banner and the scorecard's rank, which are the look of
the page rather than data.

A team's own colours come from the marts: `team_color` from the source and
`team_secondary_color` read from its logo (`scripts/derive_team_colors.py`,
into a dbt seed). When two teams are drawn together, `mart_matchup_odds`
gives each side a display colour, switching one to its secondary where the
two primaries are alike, so BYU and Michigan, both navy, are blue and maize.
A primary too light to see as a bar gives way to the secondary.

Table cell ramps stop at mid-tone, because dbt Charts writes cell text in the
same dark ink whatever the fill: every step clears APCA Lc 55 against it. The
exact values, and why, are in `meta.yml`. Bars that split on a baseline get a
`band` column naming the side, so the legend says it in words as well as
colour. `category[n]` tokens resolve against dbt Charts' built-in theme
rather than this palette, so pins use hex.

## Templates, crests and logos

`templates/` at the repository root holds the custom charts, which is where
dbt Charts looks for them:

| Template | Used on | Draws |
| --- | --- | --- |
| `court_banner.svg.j2` | every board | The header and the bar of buttons |
| `team_leaderboard.svg.j2` | Home, Rankings, Season, Tournament | Rank, crest, name with a line of detail, and a bar |
| `team_hero.svg.j2` | Scorecard | One team's name plate and national rank |
| `matchup_scoreboard.svg.j2` | Matchup | Both teams, each one's chance, and the split between them |
| `team_pair_bars.svg.j2` | Matchup | Two teams measure by measure, each in its own colour |
| `team_scatter.svg.j2` | Rankings, Season | Every team as its logo, ringed in its tier's colour (Rankings) or its own colour (Season), with the team's name on hover |

`dct describe templates/` prints each one's channels and options.

A crest is the team's abbreviation on a disc of its own colour, both straight
from `mart_team_season`. Team colour goes on the crest and nowhere else: bars
and lines take the board palette, because a school picks its colours for
itself, not so two bars can be told apart.

dbt Charts will not put an `<image>` in a custom chart, so logos are added in
the browser, by a script `scripts/render-charts.sh` puts in each page (its
source is `scripts/charts-head.html`). It reads the logos the Evidence
dashboard serves at `/evidence/logos/`, and a logo only appears once its file
has loaded, so a team without one shows no broken image. It puts them in two
kinds of place:

- **Crests** drawn by the templates (`<g class="crest"
  id="...-crest-<team_id>">`): the code gives way to the logo on a white disc,
  and the disc's colour stays as a ring. On the rankings scatter that ring
  is the tier's colour, so the grouping still reads; on the season scatter
  it is the team's own.
- **Team names** anywhere else on a board: any text that is exactly a team's
  name in the logos' `manifest.json` gets the logo in front of it. That covers
  table cells (the text moves over for it) and bar axis labels (the logo goes
  in the card's margin). Legend entries and headline-sized KPI values are
  left alone, because their space is sized to the words. Text the templates
  draw beside their own crests is marked `class="named"` so it is not done
  twice.

Every Division I team has a logo today (`dashboard/static/logos/README.md`
says from where); a team added later shows its code until that folder gains
its file.

The same script loads Oswald from Google Fonts. Every font stack that names it
falls back to a narrow system face, so a blocked request changes letterforms
and nothing else.

Boards read `marts` only, the same boundary the rest of the repository keeps. A
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

Two ways, for two jobs. `scripts/render-charts.sh` runs each board's SQL
against the warehouse and writes the drawn result to static HTML. The daily
pipeline and CI both run it, so a board whose query breaks fails a run rather
than reaching a reader, and the pipeline publishes the pages as
`charts.tar.gz` on the `warehouse-latest` release. What readers see at
`/charts` is the live server below, which draws the same boards on request.

The variables are why. `season` (on Home, Rankings, Scorecard and Season),
`team` (Scorecard and Matchup) and `opponent` (Matchup) are dropdowns and URL
parameters (`/charts/season/?season=2023-24`, `/charts/scorecard/?team=Duke
Blue Devils`), and a static export can only draw their defaults. The season
default is `Latest`, which every query resolves to the newest season with
ratings, so it moves on by itself. Each team board's `focus` CTE takes the
picked team first, then BYU, then the top-ranked team, which is also what
makes them render against the synthetic demo seasons.

## The live boards

Every board is served live, so its pickers work: `api/index.py` runs dbt
Charts' own server as a Vercel Function in a second Vercel project,
`lab-charts-live`, deployed from the repository root (`vercel.json`,
`pyproject.toml` and `uv.lock` there belong to it and to nothing else).

- It answers the seven boards and nothing else. The inspector, live reload
  and the server's own top bar are local authoring tools and are not
  exposed. `dashboard/vercel.json` rewrites every `/charts` path to it, and
  the dashboard build leaves `/charts` empty, because a static file at the
  same path would win over the rewrite.
- It downloads the published warehouse on first use and again once that copy
  is six hours old, so it is never more than a pipeline run and a few hours
  behind.
- The CDN keeps each drawn page for an hour, keyed on its URL, so a team
  someone has already opened comes back at once and only a new pick waits
  the two seconds a render takes. The first visit after a quiet spell also
  pays for the function starting and fetching the warehouse, about ten
  seconds.
- Picks live in the URL (`/charts/scorecard/?team=Duke Blue Devils&season=2025-26`),
  so a link opens on the team and season it was copied from.
