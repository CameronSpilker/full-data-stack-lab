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

# Two additions to every page's <head>, both things a board's YAML cannot say:
#
# The display face. Headings, numbers and the banner are set in Oswald, the
# condensed capitals a scoreboard uses. Every stack that names it falls back
# to a narrow system face, so a blocked font request changes letterforms and
# nothing else.
#
# Team logos. A crest drawn by templates/team_leaderboard.svg.j2 and friends is
# the team's code on a disc of its colour, inside <g class="crest"
# id="...-crest-<team_id>">. dbt Charts will not put an <image> in a custom
# chart, so the logo is added here, in the browser, the same way the Evidence
# TeamCrest does it: probe /evidence/logos/<team_id>.png, and only once it has
# loaded swap the code for the logo on a white disc ringed in the team colour.
# A team with no mirrored logo keeps its code, with no broken image and no
# layout shift, which is what lets the mirror be partial.
HEAD_EXTRA=$(cat <<'HTML'
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link id="display-face" rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600;700&display=swap">
<script id="team-logos">document.addEventListener("DOMContentLoaded",function(){var ns="http://www.w3.org/2000/svg";document.querySelectorAll('g.crest[id*="-crest-"]').forEach(function(g){var id=g.id.split("-crest-").pop(),disc=g.querySelectorAll("circle")[1],code=g.querySelector("text");if(!id||!disc)return;var src="/evidence/logos/"+encodeURIComponent(id)+".png",probe=new Image();probe.onload=function(){var cx=+disc.getAttribute("cx"),cy=+disc.getAttribute("cy"),r=+disc.getAttribute("r"),s=r*1.5,img=document.createElementNS(ns,"image");disc.setAttribute("stroke",disc.getAttribute("fill"));disc.setAttribute("stroke-width",Math.max(1.5,r/9));disc.setAttribute("fill","#ffffff");img.setAttribute("href",src);img.setAttribute("x",cx-s/2);img.setAttribute("y",cy-s/2);img.setAttribute("width",s);img.setAttribute("height",s);img.setAttribute("preserveAspectRatio","xMidYMid meet");if(code)code.remove();g.appendChild(img)};probe.src=src})});</script>
HTML
)
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
