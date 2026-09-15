"""Command line entry point: `ingest teams`, `games`, `ratings`, `lines`, `daily`, `all`, `demo`."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta

from . import cbd, demo, diagnose, load, preflight
from .config import Season, current_season, load_seasons, utc_today

log = logging.getLogger(__name__)

SOURCES = [
    "teams",
    "games",
    "ratings",
    "lines",
    "boxscores",
    "all",
    "daily",
    "demo",
    "preflight",
    "diagnose",
]

# What a scheduled run asks for: everything that changes between one night and
# the next. The team dimension is deliberately absent. Conference membership
# changes once a year, in July, which is why the Dagster schedule refreshes it
# monthly rather than nightly, and re-reading it every night spends the run's
# first requests on 365 rows that cannot have moved. That is not free: it is
# the first call the run makes, so when the source throttles it, the run dies
# there and never reaches a game.
NIGHTLY = ("games", "boxscores", "lines", "ratings")


def _wanted(source: str, extractor: str) -> bool:
    """Whether this run includes one extractor."""
    if source == "all":
        return True
    if source == "daily":
        return extractor in NIGHTLY
    return source == extractor


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ingest", description=__doc__)
    parser.add_argument(
        "source",
        choices=SOURCES,
        help=(
            "Which extractor to run. 'all' runs every live extractor. 'daily' "
            "runs the four that change overnight — games, box scores, lines "
            "and ratings — and leaves the team dimension alone, which is what "
            "a scheduled run wants. 'demo' "
            "simulates deterministic synthetic seasons so the whole pipeline "
            "runs with no network access and no API key. 'preflight' checks "
            "the live APIs against one season and writes nothing — run it "
            "before the first backfill. 'diagnose' reports why a preflight "
            "failed: what the API spec says an endpoint accepts, and what a "
            "refused request actually returned."
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
        "--since-days",
        type=int,
        metavar="N",
        help=(
            "Only extract games and lines from the last N days. What a daily "
            "run wants: last night's finals and anything corrected since, "
            "rather than the whole season re-fetched every night. Loads upsert "
            "on the row key, so a partial extract leaves the rest alone. "
            "The window also decides which seasons are asked for at all: one "
            "whose last fixture falls before it is settled and is skipped. "
            "Box scores cannot be filtered by date, so they are skipped "
            "entirely when no game was played in the window; ratings are one "
            "row per team per snapshot and are fetched for any live season."
        ),
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help=(
            "Demo only: the day the simulated world has reached. Games before "
            "it are published with a result, games after it as schedule. "
            "Defaults to today when today falls inside the current season, and "
            "otherwise to a point in the middle of conference play, so a demo "
            "run out of season still has a slate ahead of it."
        ),
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


def _still_worth_fetching(
    seasons: list[Season], since: date | None
) -> tuple[list[Season], list[Season]]:
    """Split the requested seasons into the live ones and the settled ones.

    A scheduled run asks for the current season every night, forever. That is
    right in March and pure waste in July: the 2025-26 season stopped producing
    rows on 7 April, and every run after it re-downloaded a finished season.
    The box score walk is 31 requests per season per run, which is what
    eventually got the whole pipeline rate limited into failing.

    A season is settled when its newest fixture, played or not, falls before
    the window this run is asking about. Nothing in that window means nothing
    to correct and nothing ahead to price.

    A season the warehouse knows nothing about is live, not settled. Knowing
    nothing is not the same as knowing it is over, and that is the case on a
    first run and on the night a new season is added to seasons.yml.

    Only a windowed run is filtered. A backfill passes no window because it
    means "fetch all of it", and second-guessing that would make the one
    command that exists to rebuild history quietly refuse to.
    """
    if since is None:
        return seasons, []

    live: list[Season] = []
    settled: list[Season] = []

    for season in seasons:
        latest_fixture, _ = load.season_activity(season.year)
        if latest_fixture is None or latest_fixture >= since:
            live.append(season)
        else:
            settled.append(season)

    return live, settled


def _games_landed_recently(seasons: list[Season], since: date | None) -> bool:
    """Has any of these seasons had a game played inside the window?

    The box score endpoint takes no date filter, so it cannot be asked for
    "last night" the way games and lines can: the only way to narrow it is to
    not call it. A night with no completed game behind it has no box score to
    collect, and walking 31 leagues to rediscover that is the single most
    expensive thing this run does.

    A season the warehouse knows nothing about counts as yes, for the same
    reason it counts as live: knowing nothing is not knowing there is nothing.
    A season we do know, and whose fixtures nobody has played yet, counts as
    no. Those two look alike in the data and mean opposite things, so they are
    told apart by whether a fixture is on record at all, not by whether a
    completed one is.
    """
    if since is None:
        return True

    for season in seasons:
        latest_fixture, latest_completed = load.season_activity(season.year)
        if latest_fixture is None:
            return True
        if latest_completed is not None and latest_completed >= since:
            return True

    return False


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

    # Diagnose is preflight's follow-up question and is equally read-only.
    if args.source == "diagnose":
        return diagnose.run(seasons[-1])

    if args.source == "demo":
        log.warning("Simulating SYNTHETIC seasons — these teams and results are invented.")
        tables.update(
            demo.extract(seasons, args.snapshot_date, current_season(), args.as_of)
        )

    # The team dimension is deliberately outside the season gate below.
    # Conference realignment is an offseason event, so the months when there is
    # no basketball to fetch are exactly the months when this table changes.
    if _wanted(args.source, "teams"):
        tables.update(cbd.extract_teams(current_season(), args.snapshot_date))

    since = (
        args.snapshot_date - timedelta(days=args.since_days) if args.since_days else None
    )
    if since:
        log.info("Extracting games and lines from %s onward", since)

    # Everything below is season-scoped, so a season that stopped producing
    # rows months ago is not asked for again.
    seasons, settled = _still_worth_fetching(seasons, since)
    for season in settled:
        log.info(
            "%s is settled: its last fixture is before %s, so there is nothing "
            "to correct and nothing ahead to price. Skipping it.",
            season.label,
            since,
        )

    if not seasons:
        # Not an error, and specifically not an empty extract. Returning 1 here
        # would fail the nightly pipeline every night of the offseason, which
        # is the failure this gate exists to stop.
        log.info(
            "Every requested season is settled. Nothing was fetched, and "
            "nothing needed to be. The next season resumes this on its own, "
            "the first run after its schedule lands."
        )
        return 0

    if _wanted(args.source, "games"):
        tables.update(cbd.extract_games(seasons, since=since))

    if _wanted(args.source, "boxscores"):
        # The box score endpoint takes no date filter, so it cannot be narrowed
        # to last night the way games and lines are. Not calling it is the only
        # narrowing available, and a window with no completed game in it has no
        # box score waiting at the other end.
        if _games_landed_recently(seasons, since):
            # The walk needs a league list, which normally comes from /teams.
            # What the warehouse already holds is the standby for when that
            # endpoint will not answer.
            tables.update(
                cbd.extract_box_scores(
                    seasons, fallback_conferences=load.known_conferences()
                )
            )
        else:
            log.info(
                "No game was played since %s, so there are no box scores to "
                "collect. Skipping the league walk.",
                since,
            )

    if _wanted(args.source, "lines"):
        tables.update(cbd.extract_lines(seasons, since=since))

    if _wanted(args.source, "ratings"):
        tables.update(cbd.extract_ratings(seasons, args.snapshot_date))

    counts = load.persist(tables, args.snapshot_date, replace_all=replace_all)

    for table_name, count in sorted(counts.items()):
        print(f"{table_name:20} {count:>8,} rows")

    return 0 if any(counts.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
