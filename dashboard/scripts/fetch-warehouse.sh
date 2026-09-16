#!/usr/bin/env bash
# Fetch the warehouse and the dbt docs the dashboard builds from.
#
# The daily pipeline publishes both as assets on a release that is overwritten
# in place, rather than committing a 17MB binary to git every day. The
# repository is public, so these need no credentials.
#
# Run from the dashboard directory, before `npm run sources`.
set -euo pipefail

REPO="${WAREHOUSE_REPO:-CameronSpilker/full-data-stack-lab}"
TAG="${WAREHOUSE_RELEASE:-warehouse-latest}"
BASE="https://github.com/${REPO}/releases/download/${TAG}"

mkdir -p ../data

echo "Fetching the warehouse from ${TAG}..."
if ! curl -fsSL "${BASE}/warehouse.duckdb" -o ../data/warehouse.duckdb; then
    echo "ERROR: could not download the warehouse from ${BASE}/warehouse.duckdb" >&2
    echo "The daily pipeline publishes it. Check that it has run at least once." >&2
    exit 1
fi
echo "  warehouse.duckdb ($(du -h ../data/warehouse.duckdb | cut -f1))"

# The docs are a bonus, not a blocker: a dashboard without them is still a
# dashboard, and failing the whole build over a missing link would be silly.
# They describe the models both the dashboard and the boards read, so they are
# unpacked beside the build and served from the site root at /docs.
rm -rf .site
mkdir -p .site
echo "Fetching the dbt docs..."
if curl -fsSL "${BASE}/dbt-docs.tar.gz" -o /tmp/dbt-docs.tar.gz; then
    tar -xzf /tmp/dbt-docs.tar.gz -C .site
    echo "  dbt docs unpacked to .site/docs, served at /docs"
else
    echo "  no dbt docs in the release; skipping /docs"
fi

# Same deal for the dbt charts boards. They are rendered by the pipeline
# against the warehouse it built, so what arrives here is already drawn. They
# are a separate site from the Evidence pages, so they are unpacked beside the
# build rather than into static/, and scripts/assemble-site.sh puts them on
# /charts. A release with no boards still gives a working dashboard.
echo "Fetching the dbt charts boards..."
if curl -fsSL "${BASE}/charts.tar.gz" -o /tmp/charts.tar.gz; then
    tar -xzf /tmp/charts.tar.gz -C .site
    echo "  boards unpacked to .site/charts, served at /charts"
else
    echo "  no charts in the release; skipping /charts"
fi
