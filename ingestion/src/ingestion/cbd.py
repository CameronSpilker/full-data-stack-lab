"""Extract Division I men's basketball data from collegebasketballdata.com.

CBD is the college basketball sibling of CollegeFootballData: a free, keyed API
with a published OpenAPI spec. It replaced ESPN as this project's primary
source for three reasons — a documented schema rather than an undocumented one
that shifts without notice, endpoints built for pulling a whole season at once
rather than a scoreboard walked one date at a time, and betting lines, which
give the predictor a benchmark that matters. Beating the closing spread is a
claim; going 71% straight up mostly measures whether favourites won.

An API key is required and free. Register at collegebasketballdata.com, then
set CBD_API_KEY. Without one, `ingest demo` still runs the whole pipeline.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, date, datetime
from typing import Any

import httpx

from .config import Season, request_delay, utc_today

log = logging.getLogger(__name__)

API = "https://api.collegebasketballdata.com"
USER_AGENT = "full-data-stack-lab (+https://github.com/CameronSpilker/full-data-stack-lab)"


class MissingApiKey(RuntimeError):
    """Raised when a live extract is attempted with no CBD_API_KEY set."""


def api_key() -> str:
    key = os.getenv("CBD_API_KEY")
    if not key:
        raise MissingApiKey(
            "CBD_API_KEY is not set. Get a free key at https://collegebasketballdata.com "
            "and put it in .env, or run `ingest demo` to work without network access."
        )
    return key


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=API,
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        timeout=60.0,
        follow_redirects=True,
    )


def _get(client: httpx.Client, path: str, **params: Any) -> Any:
    """GET with retries. 401 fails immediately — a bad key will not fix itself."""
    for attempt in range(5):
        try:
            response = client.get(path, params=params)
        except httpx.TransportError as exc:
            backoff = 2**attempt
            log.warning("Transport error on %s (%s); retrying in %ss", path, exc, backoff)
            time.sleep(backoff)
            continue

        if response.status_code in (401, 403):
            raise MissingApiKey(
                f"CBD rejected the API key ({response.status_code}). Check CBD_API_KEY."
            )

        if response.status_code == 429:
            wait = float(response.headers.get("retry-after", 2**attempt))
            log.warning("Rate limited on %s; sleeping %.0fs", path, wait)
            time.sleep(wait)
            continue

        if response.status_code >= 500:
            backoff = 2**attempt
            log.warning("CBD %s on %s; retrying in %ss", response.status_code, path, backoff)
            time.sleep(backoff)
            continue

        response.raise_for_status()
        time.sleep(request_delay())
        return response.json()

    raise RuntimeError(f"CBD request failed after retries: {path}")


def _first(payload: dict[str, Any], *names: str) -> Any:
    """Read the first key that is present.

    CBD's spec is stable, but its JSON is camelCase where this warehouse is
    snake_case, and a couple of fields are spelled both ways across endpoints.
    Naming every accepted spelling in one place keeps that from spreading.
    """
    for name in names:
        if name in payload and payload[name] is not None:
            return payload[name]
    return None


def _to_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Teams
# --------------------------------------------------------------------------


def parse_team(team: dict[str, Any], snapshot: date) -> dict[str, Any] | None:
    team_id = _first(team, "id", "teamId", "sourceId")
    if team_id is None:
        return None

    venue = team.get("venue") or {}
    if isinstance(venue, str):
        venue = {"name": venue}

    return {
        "snapshot_date": snapshot,
        "team_id": str(team_id),
        "team_slug": _first(team, "slug", "abbreviation"),
        "location": _first(team, "school", "team", "name", "location"),
        "mascot": _first(team, "mascot", "nickname"),
        "display_name": _first(team, "displayName", "school", "name"),
        "short_name": _first(team, "shortDisplayName", "school", "name"),
        "abbreviation": _first(team, "abbreviation", "abbr"),
        "conference_id": (
            str(_first(team, "conferenceId")) if _first(team, "conferenceId") else None
        ),
        "conference_name": _first(team, "conference", "conferenceName"),
        "venue_name": _first(venue, "name", "fullName"),
        "venue_city": _first(venue, "city"),
        "venue_state": _first(venue, "state"),
        "color": _first(team, "color", "primaryColor"),
        "is_active": True,
        "extracted_at": datetime.now(UTC),
    }


def extract_teams(
    season: Season, snapshot: date | None = None
) -> dict[str, list[dict[str, Any]]]:
    """The Division I team dimension for one season.

    Conference membership is a property of a season, not of a team, so this is
    read for the current season and stamped with a snapshot date.
    """
    snapshot = snapshot or utc_today()

    with _client() as client:
        payload = _get(client, "/teams", season=season.year)

    rows = [parsed for team in payload or [] if (parsed := parse_team(team, snapshot))]
    log.info("CBD returned %s teams for %s", len(rows), season.label)
    return {"ncaa_teams": rows}


# --------------------------------------------------------------------------
# Games
# --------------------------------------------------------------------------

# CBD labels the postseason on the game itself, so the round does not have to
# be recovered from a free-text note the way it did with ESPN.
NCAA_TOURNAMENT_TYPES = {"ncaatournament", "ncaa", "postseason"}


def parse_game(game: dict[str, Any], season_year: int) -> dict[str, Any] | None:
    game_id = _first(game, "id", "gameId")
    home_id = _first(game, "homeTeamId", "homeId")
    away_id = _first(game, "awayTeamId", "awayId")
    if game_id is None or home_id is None or away_id is None:
        return None

    start = _first(game, "startDate", "startTime", "gameDate", "date") or ""
    home_score = _to_int(_first(game, "homePoints", "homeScore"))
    away_score = _to_int(_first(game, "awayPoints", "awayScore"))
    status = str(_first(game, "status", "gameStatus") or "").lower()

    # CBD exposes the postseason label directly; `notes` is kept because it is
    # where the round name lands when the label is generic.
    game_type = str(_first(game, "seasonType", "gameType") or "").lower()
    notes = _first(game, "notes", "note", "tournament")

    return {
        "season": season_year,
        "season_type": 3 if game_type and game_type not in ("regular",) else 2,
        "game_id": str(game_id),
        "game_date": start[:10] or None,
        "tipoff_at": start or None,
        "is_neutral_site": bool(_first(game, "neutralSite", "isNeutralSite") or False),
        "is_conference_game": bool(_first(game, "conferenceGame", "isConferenceGame") or False),
        "is_completed": (
            status in ("final", "completed", "post")
            or (home_score is not None and away_score is not None)
        ),
        "status_state": status or None,
        "attendance": _to_int(_first(game, "attendance")),
        "venue_name": _first(game, "venue", "venueName"),
        "tournament_note": notes if isinstance(notes, str) else None,
        "home_team_id": str(home_id),
        "home_team_name": _first(game, "homeTeam", "homeTeamName", "home"),
        "home_team_abbreviation": _first(game, "homeAbbreviation"),
        "home_conference_id": (
            str(_first(game, "homeConferenceId")) if _first(game, "homeConferenceId") else None
        ),
        "home_score": home_score,
        "home_ap_rank": _to_int(_first(game, "homeSeed", "homeRank")),
        "home_record": None,
        "away_team_id": str(away_id),
        "away_team_name": _first(game, "awayTeam", "awayTeamName", "away"),
        "away_team_abbreviation": _first(game, "awayAbbreviation"),
        "away_conference_id": (
            str(_first(game, "awayConferenceId")) if _first(game, "awayConferenceId") else None
        ),
        "away_score": away_score,
        "away_ap_rank": _to_int(_first(game, "awaySeed", "awayRank")),
        "away_record": None,
        "extracted_at": datetime.now(UTC),
    }


def extract_games(seasons: list[Season]) -> dict[str, list[dict[str, Any]]]:
    """Every game in each requested season. One request per season."""
    rows: dict[str, dict[str, Any]] = {}

    with _client() as client:
        for season in seasons:
            try:
                payload = _get(client, "/games", season=season.year)
            except (httpx.HTTPStatusError, RuntimeError) as exc:
                log.error("Skipping games for %s: %s", season.label, exc)
                continue

            found = 0
            for game in payload or []:
                parsed = parse_game(game, season.year)
                if parsed:
                    rows[parsed["game_id"]] = parsed
                    found += 1
            log.info("CBD %s: %s games", season.label, found)

    return {"ncaa_games": list(rows.values())}


# --------------------------------------------------------------------------
# Team box scores
# --------------------------------------------------------------------------

BOX_FIELDS = {
    "field_goals_made": ("fieldGoalsMade", "fgm"),
    "field_goals_attempted": ("fieldGoalsAttempted", "fga"),
    "three_pointers_made": ("threePointFieldGoalsMade", "threePointersMade", "tpm"),
    "three_pointers_attempted": (
        "threePointFieldGoalsAttempted", "threePointersAttempted", "tpa",
    ),
    "free_throws_made": ("freeThrowsMade", "ftm"),
    "free_throws_attempted": ("freeThrowsAttempted", "fta"),
    "rebounds": ("totalRebounds", "rebounds"),
    "offensive_rebounds": ("offensiveRebounds",),
    "defensive_rebounds": ("defensiveRebounds",),
    "assists": ("assists",),
    "steals": ("steals",),
    "blocks": ("blocks",),
    "turnovers": ("turnovers", "totalTurnovers"),
    "fouls": ("fouls", "personalFouls"),
}


def parse_team_box(entry: dict[str, Any], season_year: int) -> list[dict[str, Any]]:
    """Team box lines from one `/games/teams` entry.

    CBD nests both teams under a game, with the counting stats either flat on
    the team object or under a `stats` object depending on the endpoint version.
    """
    game_id = _first(entry, "gameId", "id")
    if game_id is None:
        return []

    extracted_at = datetime.now(UTC)
    rows = []

    for side in entry.get("teams") or []:
        team_id = _first(side, "teamId", "id")
        if team_id is None:
            continue

        stats = side.get("stats") if isinstance(side.get("stats"), dict) else side

        row: dict[str, Any] = {
            "season": season_year,
            "game_id": str(game_id),
            "team_id": str(team_id),
            "team_name": _first(side, "team", "school", "teamName"),
            "extracted_at": extracted_at,
        }
        for column, names in BOX_FIELDS.items():
            row[column] = _to_int(_first(stats, *names))
        rows.append(row)

    return rows


def extract_box_scores(seasons: list[Season]) -> dict[str, list[dict[str, Any]]]:
    """Team box scores for whole seasons — one request each, not one per game."""
    rows: list[dict[str, Any]] = []

    with _client() as client:
        for season in seasons:
            try:
                payload = _get(client, "/games/teams", season=season.year)
            except (httpx.HTTPStatusError, RuntimeError) as exc:
                log.error("Skipping box scores for %s: %s", season.label, exc)
                continue

            season_rows = [
                row for entry in payload or [] for row in parse_team_box(entry, season.year)
            ]
            rows.extend(season_rows)
            log.info("CBD %s: %s box score lines", season.label, len(season_rows))

    return {"ncaa_team_box": rows}


# --------------------------------------------------------------------------
# Betting lines
# --------------------------------------------------------------------------


def parse_lines(entry: dict[str, Any], season_year: int) -> list[dict[str, Any]]:
    """One row per game per sportsbook.

    The spread is stored from the home team's perspective throughout: negative
    means the home team is favoured. Books publish it that way, but not all of
    them agree on the sign convention, so it is normalised on the way in.
    """
    game_id = _first(entry, "gameId", "id")
    if game_id is None:
        return []

    extracted_at = datetime.now(UTC)
    rows = []

    for line in entry.get("lines") or []:
        rows.append(
            {
                "season": season_year,
                "game_id": str(game_id),
                "provider": _first(line, "provider", "book") or "unknown",
                "spread": _to_float(_first(line, "spread", "homeSpread")),
                "over_under": _to_float(_first(line, "overUnder", "total")),
                "home_moneyline": _to_int(_first(line, "homeMoneyline", "moneylineHome")),
                "away_moneyline": _to_int(_first(line, "awayMoneyline", "moneylineAway")),
                "extracted_at": extracted_at,
            }
        )
    return rows


def extract_lines(seasons: list[Season]) -> dict[str, list[dict[str, Any]]]:
    """Closing betting lines — the benchmark the predictor is measured against."""
    rows: list[dict[str, Any]] = []

    with _client() as client:
        for season in seasons:
            try:
                payload = _get(client, "/lines", season=season.year)
            except (httpx.HTTPStatusError, RuntimeError) as exc:
                log.error("Skipping lines for %s: %s", season.label, exc)
                continue

            season_rows = [
                row for entry in payload or [] for row in parse_lines(entry, season.year)
            ]
            rows.extend(season_rows)
            log.info("CBD %s: %s betting lines", season.label, len(season_rows))

    return {"ncaa_betting_lines": rows}
