"""Shared configuration: the season registry and environment-driven paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# .../<repo>/ingestion/src/ingestion/config.py
_PKG = Path(__file__).resolve()
REPO_ROOT = _PKG.parents[3]
SEASONS_FILE = _PKG.parents[2] / "seasons.yml"

# ESPN groups Division I men's basketball under group 50. Without it the
# scoreboard also returns D2, D3, and exhibition games against non-D1 opponents.
D1_GROUP = "50"


@dataclass(frozen=True)
class Season:
    """One season, labelled by the calendar year it ends in."""

    year: int
    start: date
    end: date

    @property
    def label(self) -> str:
        """Human-readable form: 2026 -> '2025-26'."""
        return f"{self.year - 1}-{str(self.year)[2:]}"

    def dates(self) -> list[date]:
        """Every date in the season, oldest first. One scoreboard call each."""
        span = (self.end - self.start).days
        return [self.start + timedelta(days=offset) for offset in range(span + 1)]

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end


def _default_bounds(year: int) -> tuple[date, date]:
    """November 1 of the prior year through April 15 of the season year.

    Wide enough to cover the exhibition-adjacent opening week and the Monday
    of the national championship without needing a per-season calendar.
    """
    return date(year - 1, 11, 1), date(year, 4, 15)


def load_seasons(path: Path | None = None) -> list[Season]:
    """Read the season registry from seasons.yml."""
    payload = yaml.safe_load((path or SEASONS_FILE).read_text())
    seasons = []
    for entry in payload["seasons"]:
        year = int(entry["year"])
        start, end = _default_bounds(year)
        seasons.append(
            Season(
                year=year,
                start=entry.get("start") or start,
                end=entry.get("end") or end,
            )
        )
    return sorted(seasons, key=lambda season: season.year)


def current_season(path: Path | None = None) -> Season:
    """The season the ratings and the bracket describe."""
    payload = yaml.safe_load((path or SEASONS_FILE).read_text())
    year = int(payload["current_season"])
    for season in load_seasons(path):
        if season.year == year:
            return season
    raise ValueError(f"current_season {year} is not in the seasons list")


def _resolve(value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def raw_data_dir() -> Path:
    path = _resolve(os.getenv("RAW_DATA_DIR", "data/raw"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def duckdb_path() -> Path:
    path = _resolve(os.getenv("DUCKDB_PATH", "data/warehouse.duckdb"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def request_delay() -> float:
    """Seconds to pause between API calls.

    Neither source publishes a rate limit, so this is politeness rather than
    compliance: a full backfill is thousands of requests against free
    endpoints that owe this project nothing.
    """
    return float(os.getenv("REQUEST_DELAY_SECONDS", "0.4"))


def utc_today() -> date:
    """Today in UTC.

    Snapshot dates key the whole warehouse, so they must not depend on the
    timezone of whichever machine happens to run the pipeline.
    """
    return datetime.now(UTC).date()
