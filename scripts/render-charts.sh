#!/usr/bin/env bash
# Render every board in charts/ to a static page under dist/charts/.
#
# One definition of the render, used by the pipeline and by anyone checking
# their work locally, so what CI publishes is what was seen before the push.
#
# The layout is directory-per-board, because the pages link to each other with
# absolute paths (/charts/season/) and a static host resolves those to an
# index.html inside the folder. index.yml is the exception: it is the folder
# itself.
#
# Run from the repository root, with a warehouse at data/warehouse.duckdb.
set -euo pipefail

OUT="${1:-dist/charts}"

if [ ! -f data/warehouse.duckdb ]; then
    echo "ERROR: no warehouse at data/warehouse.duckdb." >&2
    echo "Build one with the pipeline, or fetch the published copy:" >&2
    echo "  curl -fsSL -o data/warehouse.duckdb \\" >&2
    echo "    https://github.com/CameronSpilker/full-data-stack-lab/releases/download/warehouse-latest/warehouse.duckdb" >&2
    exit 1
fi

rm -rf "$OUT"
mkdir -p "$OUT"

# meta.yml is the folder's shared style and files starting with an underscore
# are pieces boards extend, so neither is ever rendered. Everything else in
# charts/ is a page.
for board in charts/*.yml; do
    name="$(basename "$board" .yml)"
    case "$name" in
        meta|_*) continue ;;
        index) target="$OUT/index.html" ;;
        *) target="$OUT/$name/index.html" ;;
    esac

    mkdir -p "$(dirname "$target")"
    echo "  $board -> $target"

    # No --allow-chart-errors on purpose: a chart whose query broke should
    # fail the run rather than publish a page with a hole in it.
    dct render "$board" --format html --output "$target"
done

# Two additions to every page's <head>, both things a board's YAML cannot
# say. They live in scripts/charts-head.html, read in here:
#
# The display face. Headings, numbers and the banner are set in Oswald, the
# condensed capitals a scoreboard uses. Every stack that names it falls back
# to a narrow system face, so a blocked font request changes letterforms and
# nothing else.
#
# Team logos. dbt Charts will not put an <image> in a chart, so logos are
# added in the browser from the files the Evidence dashboard serves at
# /evidence/logos/, the same way its TeamCrest does it: a logo appears only
# once its file has loaded, so a team without one shows no broken image.
# Two kinds of place get one. A crest drawn by the templates (<g
# class="crest" id="...-crest-<team_id>">, the leaderboards, the scatters,
# the name plate, the scoreboard) swaps its code for the logo. And any other
# text that is exactly a team's name, looked up in the logos' manifest.json,
# gets the logo in front of it: table cells, bar labels, a KPI.
HEAD_EXTRA="$(cat scripts/charts-head.html)"
find "$OUT" -name index.html -print0 | while IFS= read -r -d '' page; do
    python3 - "$page" "$HEAD_EXTRA" <<'PY'
import sys
path, extra = sys.argv[1], sys.argv[2]
html = open(path, encoding="utf-8").read()
if 'id="team-logos"' not in html:
    html = html.replace("</head>", extra + "</head>", 1)
    open(path, "w", encoding="utf-8").write(html)
PY
done

echo "Rendered $(find "$OUT" -name '*.html' | wc -l | tr -d ' ') pages into $OUT."
