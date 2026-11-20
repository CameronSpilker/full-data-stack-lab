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

Every board opens with the same header: a navy court banner with the season it
reports on, a switch to the previous season, and seven buttons in a fixed
order, one per board, with the button for the page you are on filled in orange
rather than linked. The boards are a site of their own under `/charts`, so the
bar never links to the Evidence dashboard.

The banner is a custom chart drawn by `templates/court_banner.svg.j2`, and the
list of boards lives in that template, so adding a board means adding a row
to the table above and one line to the template. Each board extends
`_header.yml` for the query the banner reads, and still declares
`charts.banner` itself (type, template, query, height and which button it is
on), because dbt Charts checks that a chart is complete before it merges in
what a board extends. Under the banner is one line saying what the page gets
you.

On the published site the scorecard and matchup boards are fixed on one team
and one game, because these pages render to static HTML and a picker does not
survive the export. Under `dct serve` they have team pickers (see below).

`meta.yml` is not a board. dbt Charts applies it to every file in this folder,
and it carries what must not be decided per board: the look (a pale maple
floor, white cards, navy ink, and Oswald for headings and numbers the way a
scoreboard sets them), the palette (one blue, its ramp, a grey, and a red for the
bad side of a baseline), and
`title.font.case: none`, because the default is Chicago title case and the
rest of the site is sentence case. Files starting with an underscore, like
`_header.yml`, are pieces boards extend and are never rendered as pages.

## Seasons

Every board opens on the newest season and can be switched to the one before
it with the two buttons at the top right of the banner. Nothing names a year:
`_header.yml` declares a `season` variable that every board inherits, and each
query filters with

```sql
season = (SELECT coalesce(try_cast({{ season }} AS INTEGER), max(season)) FROM marts.mart_team_season)
```

so an unset variable means the latest season in that mart, and the boards
move to a new season by themselves once its first games are played.

How the switch reaches each board:

| Board | Previous season |
| --- | --- |
| Home, Rankings, Model, Season | A static copy under `/charts/<label>/`, e.g. `/charts/2025-26/rankings/`, drawn by `scripts/render-charts.sh` with `--var season=<year>` |
| Scorecard | The live board, with `?season=<year>` |
| Matchup, Tournament | Always the newest season. Odds are priced on the ratings teams carry now, and the bracket is only simulated for the season in progress |

The seasons on offer are the latest two in `mart_team_season`
(`season_options` in `_header.yml`), and the render script asks the
warehouse for the same list, so the archive moves on when a season starts.

## Colour

Colour says what kind of number it is, the same way on every board, so a
reader learns it once:

| Kind of number | Colour | Examples |
| --- | --- | --- |
| Which team, and nothing else | The team's own colours | Bars in a top-N list (Home, Season, title odds), both teams in a matchup, the rings on the season scatter |
| Any other number: a rating, a chance, simulation output | Blue | Elo lines, margin columns, seed value, the survival grid, win probability columns |
| Groups that need telling apart | One blue at three depths, darkest first | The ranking tiers (which also draw larger the higher they are), the three models |
| Signed around a baseline (zero, the median) | Blue for the good side, red for the bad side, grey for the middle | Conference depth, a team's strengths by thirds, game margins |
| A change with a direction | Blue and an up arrow when it went the good way, red and a down arrow when it did not | The scorecard's Elo over the last five games |
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

Theme tones carry the same pair: `style.tones` in `meta.yml` sets positive to
the blue and negative to the red, so a KPI change marked `good: up` or
`good: down` reads in the board's colours rather than the engine's green.

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
| `team_scatter.svg.j2` | Rankings, Season | Every team as its logo, ringed in its tier's colour (Rankings) or its own colour (Season), with a hover card and a click through to the team's scorecard |
| `team_picker.svg.j2` | Scorecard, Matchup | The team pickers, as a row under the banner |

`dct describe templates/` prints each one's channels and options.

The templates lean on what dbt Charts gives a template rather than their own
maths: `d3.scale_linear` for the scatter and pair-bar axes (the pair bars take
their ticks from the scale, so a narrow matchup gets ticks every point and a
wide one every ten), `label_ink(color)` to set a team colour as text that
clears 4.5:1 on the card (Michigan's maize prints as a deep gold), and
`style.fonts.secondary.color` for quiet text. The crests still choose their
code's ink by hand, because `label_ink` answers "this colour as text on the
card", not "which text sits on this colour".

## Reference lines and hover cards

A line a reader measures against is an annotation on the chart, not a fake
series in the query: the national median on the scorecard's strengths, a coin
flip on the matchup's gauntlet, the average team on conference depth. Each
says what it is in words beside the line. The calibration diagonal is the
exception and stays a series in its query, because annotations draw only
level and upright lines.

Where a point needs more than its two coordinates, the chart lists the extra
columns under `tooltip:`. The scorecard's Elo line names the opponent and the
result, and the reliability chart says how many games each decile stands on.
Hover cards only work on the page, so no chart's title or subtitle points at
one. The scatters are the exception, because a crowd of logos says nothing
until you ask one of them who it is. `tooltip:` is not offered to a custom
chart, so `team_scatter` takes a `details:` list of columns instead, each
already formatted by its query, and writes them into each point as hidden
text. The page script turns them into a card by the pointer (rank, record,
conference, offence, defence and net rating), and a `link` column makes the
point open that team's scorecard. On a phone the first tap shows the card
and a second one follows the link.

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

The YAML reference is [docs.dbtcharts.com](https://docs.dbtcharts.com), and
`dct skills chart` prints the same grammar in the terminal. Unknown keys are
errors rather than warnings, so `dct validate` catches most mistakes before
anything touches the warehouse. It also warns on a key that restates a
default; delete those rather than ignore them, so a board holds only what it
changes.

The dbt Charts version is pinned in `charts/requirements.txt` and
`pyproject.toml`, and `locked_schema_version` in `dbt_charts.yml` holds the
board syntax to match. An upgrade is one commit that moves all three, runs
`dct migrate charts/`, and fixes whatever `dct validate` and the render then
report. `dct migrate` skips `meta.yml`, because it is not a board, so check
that one by hand against the release notes.

## How a board reaches the site

The pages are static. `scripts/render-charts.sh` runs each board's SQL against
the warehouse and writes the drawn result to HTML, the daily pipeline publishes
that as `charts.tar.gz` on the `warehouse-latest` release, and the dashboard
build unpacks it and `dashboard/scripts/assemble-site.sh` puts it at
`/charts`. The dbt docs take the same route to `/docs`.

Two consequences worth knowing:

- A board is only as fresh as the last pipeline run, exactly like every number
  on the Evidence pages.
- Editing a board and pushing to `main` re-runs the pipeline, because
  `charts/**` is in its trigger paths. A Vercel rebuild on its own would only
  re-fetch the pages the last pipeline run drew.

Static also means the variable widgets `dct serve` gives you do not survive the
render. `scorecard.yml` has a `team` variable and `matchup.yml` has `team` and
`opponent`: under `dct serve` they are dropdowns and URL parameters
(`/scorecard/?team=Duke Blue Devils`), and the export draws their defaults.
Each board's `focus` CTE takes the picked team first, then BYU, then the
top-ranked team, which is also what makes them render against the synthetic
demo seasons. On the published site, a page that needs the reader to choose
belongs on the Evidence side, and both of those boards link to it.

## The live boards

The scorecard and matchup boards have team pickers, which a static page
cannot keep, so those two are also served live: `api/index.py` runs dbt
Charts' own server as a Vercel Function in a second Vercel project,
`lab-charts-live`, deployed from the repository root (`vercel.json`,
`pyproject.toml` and `uv.lock` there belong to it and to nothing else).

- It answers `/scorecard/` and `/matchup/` only. The inspector, live reload,
  the other boards and the server's own top bar are local authoring tools
  and are not exposed.
- It downloads the published warehouse on first use and again once that copy
  is six hours old, so it is never more than a pipeline run and a few hours
  behind.
- The CDN keeps each drawn page for an hour, keyed on its URL, so a team
  someone has already opened comes back at once and only a new pick waits
  the two seconds a render takes. The first visit after a quiet spell also
  pays for the function starting and fetching the warehouse, about ten
  seconds.
- Picks live in the URL (`/charts/scorecard/?team=Duke Blue Devils`), so a
  link opens on the team it was copied from.
- The pickers sit under the banner, not in the title row where dbt Charts
  draws a variable's control. In the title row they made it taller on these
  two boards than on the rest, so the banner, and the bar of buttons a reader
  had just pressed, moved down the page on the way in. The engine's controls
  are hidden (`visible: false`, still read from the URL), `team_picker`
  draws a field per variable, and the page script lays a native dropdown
  over each one. `meta.yml` also pins every board to 1200 wide, because a
  board otherwise hugs its widest item and Rankings came out at 1139, which
  drew its banner larger than everywhere else.
- Because a render can take seconds, every move to another page (a button,
  a season, a pick, a click on a team) starts an orange bar along the top at
  once, and a load still going after 0.6 seconds puts up a card saying what
  is loading. Static boards arrive before the card would show.
