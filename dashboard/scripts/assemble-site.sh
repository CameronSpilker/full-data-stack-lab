#!/usr/bin/env bash
# Lay out the deployed site after `evidence build`.
#
#   /            landing page, two tiles (dashboard/landing/)
#   /evidence/   the Evidence dashboard
#   /charts/     the dbt Charts boards, rewritten to the live project
#   /docs/       the dbt docs, shared by both
#
# Evidence is built with basePath /evidence, so every link and asset it emits
# already carries the prefix, but SvelteKit still writes the files flat into
# build/. This moves them under build/evidence/ to match, then adds the other
# two pieces at the root.
#
# Run from the dashboard directory, after `npm run build`.
set -euo pipefail

if [ ! -f build/index.html ]; then
    echo "ERROR: no Evidence build in build/. Run npm run build first." >&2
    exit 1
fi

mkdir -p .site
rm -rf .site/evidence
mv build .site/evidence
mkdir -p build
mv .site/evidence build/evidence
echo "  Evidence -> build/evidence"

cp -R landing/. build/
echo "  landing page -> build/"

if [ -d .site/docs ]; then
    cp -R .site/docs build/docs
    echo "  dbt docs -> build/docs"
else
    echo "  no dbt docs fetched; /docs will 404"
fi

# The dbt Charts boards are not copied in. Every board is served live, with
# its season and team pickers, by the lab-charts-live project (api/index.py at
# the repository root), and vercel.json rewrites /charts there. A static file
# at the same path would win over the rewrite, so none is put there. The
# pipeline still renders the static pages, as a check that every board draws.
echo "  dbt Charts boards: served live from lab-charts-live"
