#!/usr/bin/env bash
# Refuse to publish a warehouse the dashboard cannot open.
#
# The pipeline builds the warehouse with whatever DuckDB `dbt-duckdb` resolves
# to, and Evidence reads it with the DuckDB pinned in the dashboard's
# lockfile. Nothing kept those two in agreement, and on 15 September they
# stopped agreeing: dbt published a file that passed all 172 of its own tests,
# and every Vercel build after it died with
#
#     INTERNAL Error: Failed to load metadata pointer
#
# A warehouse that fails its tests already fails the run before publishing, so
# yesterday's complete one stays standing. A warehouse the dashboard cannot
# read deserves exactly the same treatment, and did not get it.
#
# The reader version is taken from dashboard/package-lock.json rather than
# written here, because the point is to test the DuckDB the dashboard will
# actually use. Pinning it in two places is how they drift apart again.
#
# Run from the repository root, after dbt and before publishing.
set -euo pipefail

WAREHOUSE="${1:-data/warehouse.duckdb}"

if [ ! -f "$WAREHOUSE" ]; then
    echo "ERROR: no warehouse at $WAREHOUSE to check." >&2
    exit 1
fi

# The resolved version, not the semver range in package.json: "^2.0.1" is a
# promise about the Evidence plugin, and what matters is the DuckDB underneath
# it that the lockfile actually installs.
READER_VERSION="$(python3 - <<'PY'
import json
import re
import sys

with open("dashboard/package-lock.json") as handle:
    lock = json.load(handle)

# Not `@evidence-dev/duckdb`, which is the Evidence plugin and carries its own
# version. The engine underneath it is what has to read this file, and it has
# two spellings: `@duckdb/node-bindings` since the plugin moved to
# @duckdb/node-api, and a bare `duckdb` before that, from duckdb-async.
ENGINES = ("@duckdb/node-bindings", "duckdb")


def version_of(package):
    for name, entry in lock.get("packages", {}).items():
        if name.split("node_modules/")[-1] == package and entry.get("version"):
            return entry["version"]
    return None


for engine in ENGINES:
    found = version_of(engine)
    if found:
        # The node build carries a release suffix pip has never heard of:
        # 1.4.2-r.1 is DuckDB 1.4.2 with a rebuilt binding.
        print(re.sub(r"-r\.\d+$", "", found))
        break
else:
    print(
        "no DuckDB engine in dashboard/package-lock.json: looked for "
        + " and ".join(ENGINES),
        file=sys.stderr,
    )
    sys.exit(1)
PY
)"

echo "The dashboard reads with DuckDB ${READER_VERSION}. Checking the warehouse against it..."

# Its own environment on purpose. The pipeline's DuckDB is the one that wrote
# this file, so asking it whether the file is readable answers the wrong
# question: it would say yes to a format nothing else can open.
VENV="$(mktemp -d)"
trap 'rm -rf "$VENV"' EXIT

python3 -m venv "$VENV/env"
"$VENV/env/bin/pip" install --quiet --disable-pip-version-check "duckdb==${READER_VERSION}"

"$VENV/env/bin/python" - "$WAREHOUSE" <<'PY'
import sys

import duckdb

warehouse = sys.argv[1]

try:
    connection = duckdb.connect(warehouse, read_only=True)
except Exception as exc:  # noqa: BLE001 - any failure here is the failure
    print(f"\nThe dashboard's DuckDB {duckdb.__version__} cannot open the warehouse:\n", file=sys.stderr)
    print(f"  {exc}\n", file=sys.stderr)
    print(
        "Publishing it would break every dashboard build until the next good\n"
        "run, so the run stops here and the last good warehouse stands.\n"
        "\n"
        "This is usually a storage-format mismatch: dbt wrote the file with a\n"
        "newer DuckDB than the dashboard's lockfile pins. Either bring the\n"
        "dashboard's DuckDB forward or hold dbt-duckdb back, so that the two\n"
        "agree.",
        file=sys.stderr,
    )
    raise SystemExit(1)

# Opening is not enough. The metadata for a given table is read lazily, so a
# file can open and still fail on the first mart the dashboard touches, which
# is exactly how this surfaced: as a dashboard build failure rather than a
# pipeline one.
tables = [
    row[0]
    for row in connection.execute(
        "select table_name from information_schema.tables "
        "where table_schema = 'marts' order by table_name"
    ).fetchall()
]

if not tables:
    print("\nThe warehouse opened but holds no marts. Nothing for the dashboard to read.", file=sys.stderr)
    raise SystemExit(1)

for table in tables:
    try:
        connection.execute(f'select count(*) from marts."{table}"').fetchone()
    except Exception as exc:  # noqa: BLE001
        print(f"\nmarts.{table} is unreadable by the dashboard's DuckDB:\n  {exc}", file=sys.stderr)
        raise SystemExit(1)

print(f"  all {len(tables)} marts read cleanly under DuckDB {duckdb.__version__}.")
PY
