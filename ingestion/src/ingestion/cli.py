"""Command line entry point: `ingest github`, `ingest pypi`, or `ingest all`."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from . import demo, github, load, pypi
from .config import load_tools, utc_today

log = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ingest", description=__doc__)
    parser.add_argument(
        "source",
        choices=["github", "pypi", "all", "demo"],
        help=(
            "Which extractor to run. 'demo' fabricates deterministic synthetic "
            "history so the pipeline runs with no network access."
        ),
    )
    parser.add_argument(
        "--snapshot-date",
        type=date.fromisoformat,
        default=utc_today(),
        help="Snapshot date to record and replace (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )

    tools = load_tools()
    tables: dict[str, list] = {}
    replace_all = args.source == "demo"

    if args.source == "demo":
        log.warning("Generating SYNTHETIC data — these numbers are invented.")
        tables.update(demo.extract(tools, args.snapshot_date))
    if args.source in ("github", "all"):
        tables.update(github.extract(tools, args.snapshot_date))
    if args.source in ("pypi", "all"):
        tables.update(pypi.extract(tools, args.snapshot_date))

    counts = load.persist(tables, args.snapshot_date, replace_all=replace_all)

    for table_name, count in sorted(counts.items()):
        print(f"{table_name:24} {count:>7,} rows")

    return 0 if any(counts.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
