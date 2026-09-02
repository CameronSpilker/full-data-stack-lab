"""Check the live APIs before trusting a backfill to them.

Two things in this project were written against documented schemas rather than
observed responses: the nested shape of CBD's stat objects, and the exact field
spellings collegebasketballdata.com uses. Both fail in the same quiet way — the
request succeeds, rows parse, and a column the model depends on arrives full of
nulls.

`ingest preflight` is the check that makes that loud. It runs the real
extractors against one season, writes nothing, and reports how much of each
column actually came back. Fields the pipeline cannot work without are marked
critical, and a critical field below its threshold exits non-zero.

Run this before the first real extract, and again any time a source changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from . import cbd
from .config import Season, utc_today

log = logging.getLogger(__name__)

# Columns the pipeline genuinely cannot work without, and the share of rows
# that must carry one. Anything below fails the check.
#
# The thresholds are not all 100%: a game that has not been played has no
# score, and a rating feed mid-season legitimately lacks a seed. They are set
# where a real gap stops looking like the shape of the data and starts looking
# like a parser reading the wrong column.
CRITICAL: dict[str, dict[str, float]] = {
    "ncaa_teams": {
        "team_id": 1.0,
        "location": 0.99,
    },
    "ncaa_games": {
        "game_id": 1.0,
        "game_date": 0.99,
        "home_team_id": 1.0,
        "away_team_id": 1.0,
    },
    "ncaa_ratings": {
        # The rating the entire predictor rests on, and the id that joins it to
        # every other table in the warehouse.
        "team_id": 1.0,
        "team_name": 1.0,
        "adj_oe": 0.95,
        "adj_de": 0.95,
        "adj_tempo": 0.90,
    },
    "ncaa_betting_lines": {
        "game_id": 1.0,
        "spread": 0.95,
    },
    "ncaa_team_box": {
        "game_id": 1.0,
        "team_id": 1.0,
        "field_goals_attempted": 0.95,
    },
}


@dataclass
class Check:
    table: str
    column: str
    coverage: float
    rows: int
    threshold: float | None

    @property
    def is_critical(self) -> bool:
        return self.threshold is not None

    @property
    def failed(self) -> bool:
        return self.is_critical and self.coverage < self.threshold


def coverage(rows: list[dict[str, Any]], table: str) -> list[Check]:
    """Share of rows carrying a non-null value, for every column."""
    if not rows:
        return []

    thresholds = CRITICAL.get(table, {})
    columns = sorted({column for row in rows for column in row})
    checks = []

    for column in columns:
        present = sum(1 for row in rows if row.get(column) is not None)
        checks.append(
            Check(
                table=table,
                column=column,
                coverage=present / len(rows),
                rows=len(rows),
                threshold=thresholds.get(column),
            )
        )
    return checks


def _report(table: str, checks: list[Check]) -> None:
    if not checks:
        print(f"\n  {table:22} NO ROWS RETURNED")
        return

    print(f"\n  {table:22} {checks[0].rows:>7,} rows")
    for check in sorted(checks, key=lambda c: (not c.is_critical, c.column)):
        if check.failed:
            mark = "FAIL"
        elif check.is_critical:
            mark = "crit"
        elif check.coverage == 0:
            mark = "empty"
        else:
            mark = ""
        print(f"      {check.column:32} {check.coverage:7.1%}  {mark}")


def run(season: Season, snapshot: date | None = None) -> int:
    """Extract one season from every source and report column coverage."""
    snapshot = snapshot or utc_today()
    all_checks: list[Check] = []

    print(f"\nPreflight against {season.label} (season {season.year}). Nothing is written.")

    sources = [
        ("collegebasketballdata.com /teams", lambda: cbd.extract_teams(season, snapshot)),
        ("collegebasketballdata.com /games", lambda: cbd.extract_games([season])),
        ("collegebasketballdata.com /games/teams", lambda: cbd.extract_box_scores([season])),
        ("collegebasketballdata.com /lines", lambda: cbd.extract_lines([season])),
        (
            "collegebasketballdata.com /ratings/adjusted",
            lambda: cbd.extract_ratings([season], snapshot),
        ),
    ]

    for label, extract in sources:
        print(f"\n{label}")
        try:
            tables = extract()
        # Broad on purpose: a preflight exists to report every failure in one
        # pass, not to stop at the first source that is down.
        except Exception as exc:
            print(f"  FAILED: {type(exc).__name__}: {exc}")
            all_checks.append(
                Check(table=label, column="(request)", coverage=0.0, rows=0, threshold=1.0)
            )
            continue

        for table, rows in tables.items():
            checks = coverage(rows, table)
            all_checks.extend(checks)
            _report(table, checks)
            if not rows:
                all_checks.append(
                    Check(table=table, column="(rows)", coverage=0.0, rows=0, threshold=1.0)
                )

    failures = [check for check in all_checks if check.failed]

    print("\n" + "-" * 68)
    if failures:
        print(f"{len(failures)} critical field(s) below threshold:\n")
        for check in failures:
            print(
                f"  {check.table}.{check.column}: {check.coverage:.1%} "
                f"(needs {check.threshold:.0%})"
            )
        print(
            "\nA field at or near 0% means the parser is reading the wrong key or the\n"
            "wrong column. Add the real field name to the tuple in `_first()`, or check\n"
            "the nested group it is read from in BOX_FIELDS. `ingest diagnose` prints\n"
            "for that column in cbd.py. Do not run a backfill until this is clean."
        )
        return 1

    print("Every critical field came back populated. Safe to run the backfill.")
    return 0
