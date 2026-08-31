#!/usr/bin/env python
"""Run every Evidence query against the built warehouse.

Evidence resolves its SQL at build time, so a mart column that gets renamed
shows up as a broken dashboard rather than a failed dbt run. This closes that
gap cheaply: it executes each source query and each page query directly
against DuckDB and fails on the first one that does not run.

It checks the SQL, not the rendering — a full `evidence build` still catches
component and layout errors.

    python scripts/validate_dashboard_queries.py
"""

from __future__ import annotations

import os
import pathlib
import re
import sys

import duckdb

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES_DIR = REPO_ROOT / "dashboard" / "sources" / "warehouse"
PAGES_DIR = REPO_ROOT / "dashboard" / "pages"

# Evidence interpolates params and inputs at render time. Substituting a real
# id rather than a dummy means a templated page's queries are checked against
# rows that actually exist, so a broken filter fails here instead of rendering
# an empty page.
PLACEHOLDER_QUERY = "select team_id from marts.mart_team_season limit 1"
FALLBACK_PLACEHOLDER = "1001"


def main() -> int:
    warehouse = REPO_ROOT / os.getenv("DUCKDB_PATH", "data/warehouse.duckdb")
    if not warehouse.exists():
        print(f"No warehouse at {warehouse}. Run `ingest demo` then `dbt build` first.")
        return 1

    con = duckdb.connect(str(warehouse), read_only=True)
    sources: dict[str, str] = {}
    failures: list[str] = []

    try:
        placeholder = str(con.execute(PLACEHOLDER_QUERY).fetchone()[0])
    except (duckdb.Error, TypeError):
        placeholder = FALLBACK_PLACEHOLDER

    for path in sorted(SOURCES_DIR.glob("*.sql")):
        sql = path.read_text()
        try:
            rows = con.execute(sql).fetchall()
            sources[path.stem] = sql
            print(f"ok   source {path.name:30} {len(rows):>6} rows")
        except duckdb.Error as exc:
            failures.append(f"{path.name}: {exc}")
            print(f"FAIL source {path.name}: {exc}")

    for page in sorted(PAGES_DIR.rglob("*.md")):
        rel = page.relative_to(REPO_ROOT)
        for name, block in re.findall(r"```sql (\w+)\n(.*?)```", page.read_text(), re.DOTALL):
            probe = re.sub(r"\$\{[^}]+\}", placeholder, block)
            for source_name, source_sql in sources.items():
                probe = re.sub(
                    rf"(?<=\b(?:from|join)\s){source_name}\b", f"({source_sql})", probe
                )
            try:
                con.execute(probe).fetchall()
                print(f"ok   query  {rel}:{name}")
            except duckdb.Error as exc:
                failures.append(f"{rel}:{name}: {exc}")
                print(f"FAIL query  {rel}:{name}: {exc}")

    if failures:
        print(f"\n{len(failures)} dashboard queries failed.")
        return 1

    print("\nEvery dashboard query runs against the warehouse.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
