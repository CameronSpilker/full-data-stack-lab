#!/usr/bin/env bash
# Rewrite the built warehouse in a storage format the dashboard can open.
#
# DuckDB files carry the storage format of whatever wrote them, and a reader
# older than that format cannot open the file at all. dbt writes with whatever
# DuckDB `dbt-duckdb` resolves to, which floats; Evidence reads with the one
# its lockfile pins. On 15 September those diverged far enough to matter: the
# published warehouse needed DuckDB 1.4 or newer, Evidence had 1.1.3, and
# every dashboard build died on
#
#     INTERNAL Error: Failed to load metadata pointer
#
# Pinning dbt's writer would not have saved it. The format belongs to the
# file, so a run that starts from an already-newer warehouse keeps writing a
# newer one, and the pipeline starts from the warehouse it published
# yesterday. The loop only breaks by rewriting the file.
#
# So the last thing to touch the warehouse is a full copy into a fresh
# database pinned to an old storage version. `COPY FROM DATABASE` carries
# every schema, table and view across, and the copy is compacted on the way:
# the file that prompted this shrank from 51MB to 28MB, which the dashboard
# has to download on every build.
#
# Deliberately unconditional. Doing it only when the check fails would leave
# the normal path untested, and this is the path that has to work on the one
# night the formats drift.
#
# Run from the repository root, after dbt and before publishing.
set -euo pipefail

WAREHOUSE="${1:-data/warehouse.duckdb}"

if [ ! -f "$WAREHOUSE" ]; then
    echo "ERROR: no warehouse at $WAREHOUSE to normalise." >&2
    exit 1
fi

BEFORE="$(du -h "$WAREHOUSE" | cut -f1)"

python3 - "$WAREHOUSE" <<'PY'
import os
import sys

import duckdb

warehouse = sys.argv[1]
rewritten = f"{warehouse}.normalised"

for leftover in (rewritten, f"{rewritten}.wal"):
    if os.path.exists(leftover):
        os.remove(leftover)

# v0.10.2 is DuckDB's own conservative default rather than a number picked
# here. Anything newer than it can read the result, so this stays correct if
# the dashboard's DuckDB moves forward; it is the floor, not a target.
connection = duckdb.connect(config={"storage_compatibility_version": "v0.10.2"})
connection.execute(f"ATTACH '{warehouse}' AS source (READ_ONLY)")
connection.execute(f"ATTACH '{rewritten}' AS rewritten")
connection.execute("COPY FROM DATABASE source TO rewritten")
connection.execute("DETACH source")
connection.execute("DETACH rewritten")
connection.close()

# Replaced only once the copy is complete, so an interrupted run leaves the
# warehouse it started with rather than half of a new one.
os.replace(rewritten, warehouse)
wal = f"{rewritten}.wal"
if os.path.exists(wal):
    os.remove(wal)
PY

echo "Normalised the warehouse storage format: ${BEFORE} -> $(du -h "$WAREHOUSE" | cut -f1)."
