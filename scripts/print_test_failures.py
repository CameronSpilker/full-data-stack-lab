"""Print the rows behind a failed dbt test.

`dbt build --store-failures` writes each failing test's offending rows to a
table instead of only reporting a count. A count says a test failed; the rows
say whether the data is wrong, the test is wrong, or the world is stranger than
either assumed. In a scheduled pipeline nobody is watching the terminal, so the
rows have to reach the log or they are lost with the runner.

Usage: python scripts/print_test_failures.py [limit]
"""

from __future__ import annotations

import os
import sys

import duckdb

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 25
PATH = os.getenv("DUCKDB_PATH", "data/warehouse.duckdb")


def main() -> int:
    if not os.path.exists(PATH):
        print(f"No warehouse at {PATH}; nothing to report.")
        return 0

    connection = duckdb.connect(PATH, read_only=True)

    # dbt puts stored failures in a schema whose name ends in the audit
    # suffix, whatever the target schema is called.
    tables = connection.execute(
        """
        select table_schema, table_name
        from information_schema.tables
        where table_schema ilike '%dbt_test__audit%'
        order by table_schema, table_name
        """
    ).fetchall()

    if not tables:
        print("No stored test failures found. Was dbt run with --store-failures?")
        return 0

    for schema, table in tables:
        rows = connection.execute(
            f'select * from "{schema}"."{table}" limit {LIMIT}'
        ).fetchall()
        if not rows:
            continue

        columns = [d[0] for d in connection.description]
        total = connection.execute(f'select count(*) from "{schema}"."{table}"').fetchone()[0]

        print(f"\n{'=' * 78}\n{table}  ({total} failing row{'s' if total != 1 else ''})\n{'=' * 78}")
        print("  " + " | ".join(columns))
        print("  " + "-" * 74)
        for row in rows:
            print("  " + " | ".join("" if value is None else str(value) for value in row))
        if total > len(rows):
            print(f"  ... and {total - len(rows)} more")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
