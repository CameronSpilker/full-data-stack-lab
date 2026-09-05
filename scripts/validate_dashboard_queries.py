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

# Evidence lets one query reference another by name: `from ${other_query}`
# inlines that query's results. That has to be resolved before the placeholder
# substitution below, or a chained reference turns into `from 1080` and fails
# here while working perfectly well in the built dashboard.
QUERY_REF = re.compile(r"\$\{(\w+)\}")
MAX_CHAIN_DEPTH = 8

# A component binds to a query by name, and Evidence scopes queries to the page
# that declares them. Binding to one that is not declared there fails the build
# with "'name' is not defined", which is a slow and unhelpful way to find a
# typo, or a block deleted by an edit that meant to leave it alone. Every query
# on a page can run perfectly well and the page still not build, so running the
# SQL is not enough on its own.
DATA_BINDING = re.compile(r"data=\{(\w+)\}")


def resolve_chain(sql: str, blocks: dict[str, str], depth: int = 0) -> str:
    """Inline every ${query_name} reference to another block on the same page."""
    if depth > MAX_CHAIN_DEPTH:
        raise ValueError("query references are cyclic")

    def replace(match: re.Match[str]) -> str:
        referenced = blocks.get(match.group(1))
        if referenced is None:
            # Not a chained query: an input or a route param, left for the
            # placeholder substitution to handle.
            return match.group(0)
        return f"({resolve_chain(referenced, blocks, depth + 1)})"

    return QUERY_REF.sub(replace, sql)


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
        text = page.read_text()
        found = re.findall(r"```sql (\w+)\n(.*?)```", text, re.DOTALL)
        blocks = dict(found)

        for name in sorted(set(DATA_BINDING.findall(text)) - set(blocks)):
            failures.append(f"{rel}: data={{{name}}} is not declared on this page")
            print(f"FAIL ref    {rel}: data={{{name}}} is not declared on this page")

        for name, block in found:
            try:
                probe = resolve_chain(block, blocks)
            except ValueError as exc:
                failures.append(f"{rel}:{name}: {exc}")
                print(f"FAIL query  {rel}:{name}: {exc}")
                continue
            probe = re.sub(r"\$\{[^}]+\}", placeholder, probe)
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
