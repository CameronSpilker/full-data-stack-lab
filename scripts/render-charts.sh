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

# meta.yml is the folder's shared style, not a board, so it is never rendered.
# Everything else in charts/ is a page.
for board in charts/*.yml; do
    name="$(basename "$board" .yml)"
    case "$name" in
        meta) continue ;;
        index) target="$OUT/index.html" ;;
        *) target="$OUT/$name/index.html" ;;
    esac

    mkdir -p "$(dirname "$target")"
    echo "  $board -> $target"

    # No --allow-chart-errors on purpose: a chart whose query broke should
    # fail the run rather than publish a page with a hole in it.
    dct render "$board" --format html --output "$target"
done

echo "Rendered $(find "$OUT" -name '*.html' | wc -l | tr -d ' ') pages into $OUT."
