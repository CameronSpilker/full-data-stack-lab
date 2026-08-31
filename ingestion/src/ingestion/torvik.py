"""Extract adjusted efficiency ratings from Barttorvik's T-Rank.

Game scores say what happened. They do not say how good a team is: a 20-point
win over the worst team in the country is worth less than a close loss at
Houston. Adjusted efficiency is the correction — points scored and allowed per
100 possessions, adjusted for opponent and site — and Barttorvik publishes it
for free, which KenPom does not.

The export is a CSV. Barttorvik has historically served it both with and
without a header row, so this reads it both ways: by column name when a header
is present, positionally against a documented map when it is not. If neither
works the run fails loudly rather than silently loading a column of garbage
into the rating the whole predictor rests on.
"""

from __future__ import annotations

import csv
import io
import logging
import time
from datetime import UTC, date, datetime
from typing import Any

import httpx

from .config import Season, request_delay, utc_today

log = logging.getLogger(__name__)

BASE = "https://barttorvik.com"
USER_AGENT = "full-data-stack-lab (+https://github.com/CameronSpilker/full-data-stack-lab)"

# The warehouse's column names, mapped to every header spelling Barttorvik has
# used for them. Matching is case-insensitive and ignores spaces and
# underscores, so "AdjOE", "adj_oe", and "adj oe" all resolve to adj_oe.
HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "team_name": ("team", "teamname"),
    "conference": ("conf", "conference"),
    "games": ("g", "games"),
    "wins": ("w", "wins", "rec"),
    "losses": ("l", "losses"),
    "adj_oe": ("adjoe", "adjo", "adjoff", "oe"),
    "adj_de": ("adjde", "adjd", "adjdef", "de"),
    "barthag": ("barthag", "bart"),
    "adj_tempo": ("adjt", "adjtempo", "tempo"),
    "efg_pct": ("efg", "efgpct", "efg%"),
    "efg_pct_allowed": ("efgd", "efgdpct", "defefg", "efgd%"),
    "turnover_pct": ("tor", "tovpct", "to%"),
    "turnover_pct_forced": ("tord", "tovpctd", "tod%"),
    "off_reb_pct": ("orb", "orbpct", "oreb%"),
    "def_reb_pct": ("drb", "drbpct", "dreb%"),
    "ft_rate": ("ftr", "ftrate"),
    "ft_rate_allowed": ("ftrd", "ftrated"),
    "two_pt_pct": ("2ppct", "2p", "twoppct"),
    "two_pt_pct_allowed": ("2ppctd", "2pd", "twoppctd"),
    "three_pt_pct": ("3ppct", "3p", "threeppct"),
    "three_pt_pct_allowed": ("3ppctd", "3pd", "threeppctd"),
    "wab": ("wab",),
    "seed": ("seed",),
}

# Barttorvik's headerless T-Rank export, in order. Only the columns this
# project uses are named; the rest are placeholders so the positions line up.
# VERIFY THIS AGAINST A LIVE RESPONSE before trusting a headerless parse — it
# is the single most likely place this ingestion breaks.
POSITIONAL_COLUMNS: tuple[str | None, ...] = (
    "team_name",
    "conference",
    "games",
    "wins",
    "adj_oe",
    None,  # adj_oe rank
    "adj_de",
    None,  # adj_de rank
    "barthag",
    "efg_pct",
    "efg_pct_allowed",
    "ft_rate",
    "ft_rate_allowed",
    "turnover_pct",
    "turnover_pct_forced",
    "off_reb_pct",
    "def_reb_pct",
    "two_pt_pct",
    "two_pt_pct_allowed",
    "three_pt_pct",
    "three_pt_pct_allowed",
    "adj_tempo",
    None,
    "wab",
)

NUMERIC_COLUMNS = {
    name
    for name in HEADER_ALIASES
    if name not in ("team_name", "conference")
}


def _normalize(header: str) -> str:
    return header.strip().lower().replace(" ", "").replace("_", "").replace(".", "")


def _looks_like_header(row: list[str]) -> bool:
    """A header row has a recognisable rating name and no leading team score."""
    normalized = {_normalize(cell) for cell in row}
    return bool(normalized & {"adjoe", "adjo", "barthag", "team", "adjde"})


def _to_number(value: str) -> float | None:
    try:
        return float(value.strip().replace("%", ""))
    except (TypeError, ValueError, AttributeError):
        return None


def _blank_row() -> dict[str, Any]:
    return {name: None for name in HEADER_ALIASES}


def _from_header(rows: list[list[str]]) -> list[dict[str, Any]]:
    lookup: dict[int, str] = {}
    for index, cell in enumerate(rows[0]):
        normalized = _normalize(cell)
        for column, aliases in HEADER_ALIASES.items():
            if normalized in aliases and column not in lookup.values():
                lookup[index] = column
                break

    log.info("Barttorvik header matched %s of %s columns", len(lookup), len(HEADER_ALIASES))
    parsed = []
    for raw in rows[1:]:
        row = _blank_row()
        for index, column in lookup.items():
            if index < len(raw):
                row[column] = raw[index]
        parsed.append(row)
    return parsed


def _from_position(rows: list[list[str]]) -> list[dict[str, Any]]:
    log.warning(
        "Barttorvik returned no header; falling back to the positional column map. "
        "Confirm the mapping is still correct."
    )
    parsed = []
    for raw in rows:
        row = _blank_row()
        for index, column in enumerate(POSITIONAL_COLUMNS):
            if column and index < len(raw):
                row[column] = raw[index]
        parsed.append(row)
    return parsed


def parse_ratings(payload: str, season_year: int, snapshot: date) -> list[dict[str, Any]]:
    """Turn a T-Rank CSV into rating rows, one per team."""
    rows = [row for row in csv.reader(io.StringIO(payload)) if row and any(cell for cell in row)]
    if not rows:
        raise ValueError(f"Barttorvik returned no rows for {season_year}")

    parsed = _from_header(rows) if _looks_like_header(rows[0]) else _from_position(rows)

    ratings: list[dict[str, Any]] = []
    for row in parsed:
        team_name = (row.get("team_name") or "").strip()
        if not team_name:
            continue

        # Some exports carry the record as "31-6" in the wins column rather
        # than splitting wins and losses.
        wins, losses = row.get("wins"), row.get("losses")
        if isinstance(wins, str) and "-" in wins and losses is None:
            wins, _, losses = wins.partition("-")

        record = {
            "snapshot_date": snapshot,
            "season": season_year,
            "team_name": team_name,
            "conference": (row.get("conference") or "").strip() or None,
            "wins": _to_number(wins) if wins is not None else None,
            "losses": _to_number(losses) if losses is not None else None,
            "extracted_at": datetime.now(UTC),
        }
        for column in NUMERIC_COLUMNS:
            if column in ("wins", "losses"):
                continue
            value = row.get(column)
            record[column] = _to_number(value) if value is not None else None

        ratings.append(record)

    if not ratings:
        raise ValueError(f"Barttorvik CSV for {season_year} parsed to zero teams")

    # Adjusted efficiency is the input to every prediction. If it did not
    # parse, the run has produced a table that looks fine and predicts noise.
    rated = sum(1 for row in ratings if row["adj_oe"] is not None)
    if rated < len(ratings) * 0.9:
        raise ValueError(
            f"Only {rated}/{len(ratings)} Barttorvik rows for {season_year} carry adj_oe. "
            "The CSV layout has probably changed; check HEADER_ALIASES and POSITIONAL_COLUMNS."
        )

    return ratings


def fetch_season(client: httpx.Client, season: Season) -> str:
    for attempt in range(4):
        response = client.get("/trank.php", params={"year": season.year, "csv": 1})
        if response.status_code >= 500:
            time.sleep(2**attempt)
            continue
        response.raise_for_status()
        time.sleep(request_delay())
        return response.text
    raise RuntimeError(f"Barttorvik request failed after retries: {season.year}")


def extract(
    seasons: list[Season], snapshot: date | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Adjusted efficiency ratings for every requested season."""
    snapshot = snapshot or utc_today()
    rows: list[dict[str, Any]] = []

    with httpx.Client(
        base_url=BASE,
        headers={"User-Agent": USER_AGENT},
        timeout=60.0,
        follow_redirects=True,
    ) as client:
        for season in seasons:
            try:
                payload = fetch_season(client, season)
                parsed = parse_ratings(payload, season.year, snapshot)
                rows.extend(parsed)
                log.info("Barttorvik %s: %s teams", season.label, len(parsed))
            except (httpx.HTTPStatusError, RuntimeError, ValueError) as exc:
                log.error("Skipping Barttorvik %s: %s", season.year, exc)

    return {"ncaa_ratings": rows}
