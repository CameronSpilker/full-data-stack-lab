"""Open the warehouse the way the dashboard will, and fail if it cannot.

The pipeline writes this file with one DuckDB and the dashboard reads it with
another: the engine inside `@evidence-dev/duckdb`, pinned in
`dashboard/package-lock.json`. Those two are separate dependencies that move on
their own schedules, and a file the writer is perfectly happy with is not
automatically one the reader can open.

That gap took the site down in September 2026. The pipeline's DuckDB floated up
to 1.5 while the dashboard's was still 1.0, and every Vercel build failed on
the connection:

    Error connecting to datasource warehouse: INTERNAL Error:
    Failed to load metadata pointer (id 47, idx 10, ptr 720575940379279407)

Nothing before that step noticed. dbt built and tested the warehouse, the
charts rendered against it, and the run went green. CI could not have caught it
either: the warehouse CI builds is small and written in one pass, and a file
like that reads fine on every version. Only the published one, months old and
rewritten every night, carries the layout the older reader gives up on.

So the check runs here, against the file that is about to be published, under a
DuckDB pinned to the dashboard's. Run it before the upload and a warehouse the
dashboard cannot read is never the one on the release.

Usage: python scripts/check_warehouse_opens.py data/warehouse.duckdb
"""

import sys
from pathlib import Path

import duckdb

# Reading the catalog is what fails when the reader cannot follow the file, so
# opening it is most of the test. Counting the marts is the rest: an empty
# catalog opens cleanly and is still not a warehouse.
MARTS_SCHEMA = "marts"


def check(path: Path) -> int:
    if not path.exists():
        print(f"ERROR: no warehouse at {path}.", file=sys.stderr)
        return 1

    print(f"Opening {path} with DuckDB {duckdb.__version__}, the dashboard's reader.")

    try:
        with duckdb.connect(str(path), read_only=True) as con:
            marts = con.execute(
                "select table_name from information_schema.tables "
                "where table_schema = ? order by table_name",
                [MARTS_SCHEMA],
            ).fetchall()
    except duckdb.Error as exc:
        print(f"ERROR: the dashboard's DuckDB cannot read {path}:", file=sys.stderr)
        print(f"  {exc}", file=sys.stderr)
        print(
            "This is the failure the Vercel build would hit, so the warehouse is "
            "not being published. The writer and the reader have drifted apart: "
            "compare the DuckDB the pipeline installs against the one in "
            "dashboard/package-lock.json, and move the reader forward.",
            file=sys.stderr,
        )
        return 1

    if not marts:
        print(
            f"ERROR: {path} opened but holds no {MARTS_SCHEMA} tables, so there is "
            "nothing for the dashboard to read.",
            file=sys.stderr,
        )
        return 1

    print(f"  {len(marts)} marts, readable: {', '.join(name for (name,) in marts)}")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    return check(Path(sys.argv[1]))


if __name__ == "__main__":
    raise SystemExit(main())
