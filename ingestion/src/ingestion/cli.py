"""Command line entry point.

`ingest demo` simulates seasons offline. `ingest preflight` checks the live
APIs and writes nothing. `ingest all` runs every extractor for real; the
individual sources — teams, games, ratings, lines, boxscores — run alone.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from . import cbd, demo, load, preflight, torvik
from .config import Season, current_season, load_seasons, utc_today

log = logging.getLogger(__name__)

SOURCES = ["teams", "games", "ratings", "lines", "boxscores", "all", "demo", "preflight"]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ingest", description=__doc__)
    parser.add_argument(
        "source",
        choices=SOURCES,
        help=(
            "Which extractor to run. 'all' runs every live extractor. 'demo' "
            "simulates deterministic synthetic seasons so the whole pipeline "
            "runs with no network access and no API key. 'preflight' checks "
            "the live APIs against one season and writes nothing — run it "
            "before the first backfill."
        ),
    )
    parser.add_argument(
        "--season",
        type=int,
        action="append",
        dest="seasons",
        help=(
            "Season to extract, by the year it ends in (2026 is 2025-26). "
            "Repeatable. Defaults to every season in seasons.yml."
        ),
    )
    parser.add_argument(
        "--current-only",
        action="store_true",
        help="Shorthand for --season <current_season>, for a routine in-season run.",
    )
    parser.add_argument(
        "--snapshot-date",
        type=date.fromisoformat,
        default=utc_today(),
        help="Snapshot date to record (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args(argv)


def _selected_seasons(args: argparse.Namespace) -> list[Season]:
    every = load_seasons()
    if args.current_only:
        return [current_season()]
    if not args.seasons:
        return every

    wanted = set(args.seasons)
    chosen = [season for season in every if season.year in wanted]
    missing = wanted - {season.year for season in chosen}
    if missing:
        raise SystemExit(
            f"Season(s) {sorted(missing)} are not in seasons.yml. Add them there first."
        )
    return chosen


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )

    seasons = _selected_seasons(args)
    tables: dict[str, list] = {}
    replace_all = args.source == "demo"

    # A preflight reports on the live sources and writes nothing, so it
    # returns before the loading path rather than through it.
    if args.source == "preflight":
        return preflight.run(seasons[-1], args.snapshot_date)

    if args.source == "demo":
        log.warning("Simulating SYNTHETIC seasons — these teams and results are invented.")
        tables.update(demo.extract(seasons, args.snapshot_date, current_season()))

    if args.source in ("teams", "all"):
        tables.update(cbd.extract_teams(current_season(), args.snapshot_date))

    if args.source in ("games", "all"):
        tables.update(cbd.extract_games(seasons))

    if args.source in ("boxscores", "all"):
        tables.update(cbd.extract_box_scores(seasons))

    if args.source in ("lines", "all"):
        tables.update(cbd.extract_lines(seasons))

    if args.source in ("ratings", "all"):
        tables.update(torvik.extract(seasons, args.snapshot_date))

    counts = load.persist(tables, args.snapshot_date, replace_all=replace_all)

    for table_name, count in sorted(counts.items()):
        print(f"{table_name:20} {count:>8,} rows")

    return 0 if any(counts.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
