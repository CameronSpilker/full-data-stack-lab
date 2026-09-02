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
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from .config import Season, request_delay, utc_today

log = logging.getLogger(__name__)

API = "https://api.collegebasketballdata.com"
USER_AGENT = "full-data-stack-lab (+https://github.com/CameronSpilker/full-data-stack-lab)"


class MissingApiKey(RuntimeError):
    """Raised when a live extract is attempted with no CBD_API_KEY set."""


class SourceExhausted(RuntimeError):
    """Every request for one source failed.

    An extractor that loses a season logs it and carries on, because one bad
    response should not cost the other four. Losing every season is a different
    event: it means the source returned nothing at all, and a run that treats
    that as "no news" writes a warehouse missing a whole table while reporting
    success. This is raised instead, so the run fails before it publishes and
    yesterday's complete warehouse stands.
    """


# A general fault gets five tries. A rate limit is not a fault: it is the
# expected answer when a five-season backfill asks for everything at once, so
# it gets its own budget and a longer ceiling. Worst case is about two minutes
# of waiting on one request before the source is called exhausted.
MAX_ATTEMPTS = 5
RATE_LIMIT_ATTEMPTS = 7
RATE_LIMIT_MAX_WAIT = 30.0


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
    """GET with retries. 401 fails immediately: a bad key will not fix itself.

    A 429 does not spend an attempt. Backing off five times in thirty-one
    seconds and giving up is what lost four seasons of betting lines and
    ratings on the first successful backfill: the waits were shorter than the
    window the limit was measured over, so every retry arrived still throttled.
    """
    attempt = 0
    throttled = 0

    while attempt < MAX_ATTEMPTS:
        try:
            response = client.get(path, params=params)
        except httpx.TransportError as exc:
            backoff = 2**attempt
            attempt += 1
            log.warning("Transport error on %s (%s); retrying in %ss", path, exc, backoff)
            time.sleep(backoff)
            continue

        if response.status_code in (401, 403):
            raise MissingApiKey(
                f"CBD rejected the API key ({response.status_code}). Check CBD_API_KEY."
            )

        if response.status_code == 429:
            throttled += 1
            if throttled > RATE_LIMIT_ATTEMPTS:
                raise RuntimeError(
                    f"CBD is still rate limiting {path} after {RATE_LIMIT_ATTEMPTS} waits"
                )
            wait = min(
                float(response.headers.get("retry-after", 2**throttled)),
                RATE_LIMIT_MAX_WAIT,
            )
            log.warning("Rate limited on %s; sleeping %.0fs", path, wait)
            time.sleep(wait)
            continue

        if response.status_code >= 500:
            backoff = 2**attempt
            attempt += 1
            log.warning("CBD %s on %s; retrying in %ss", response.status_code, path, backoff)
            time.sleep(backoff)
            continue

        response.raise_for_status()
        time.sleep(request_delay())
        return response.json()

    raise RuntimeError(f"CBD request failed after retries: {path}")


def _require_a_season(source: str, seasons: list[Season], failed: int) -> None:
    """Fail the extract if not one requested season came back.

    Losing some seasons is survivable and already logged. Losing all of them
    means the warehouse would keep whatever it had for this source and the run
    would still report success, which is how a backfill can publish a table
    that is four seasons short without anyone noticing.
    """
    if seasons and failed == len(seasons):
        raise SourceExhausted(
            f"Every request for {source} failed across all {len(seasons)} seasons. "
            "Nothing was extracted, so nothing is published."
        )


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
# Paging
# --------------------------------------------------------------------------

# CBD truncates a response at 3,000 records. It does not say so: the request
# succeeds, the JSON is well formed, and the season simply stops in January.
# A whole season of Division I basketball is roughly 6,000 games, so every
# season-wide request has to be split into windows small enough to come back
# under the ceiling.
PAGE_LIMIT = 3000


def _windows(season: Season, days: int = 14, since: date | None = None) -> list[tuple[date, date]]:
    """The season cut into fixed windows, oldest first.

    `since` trims the walk to recent history, which is what a daily run wants:
    yesterday's finals and any score corrected since, rather than five months
    of settled results re-fetched every night.
    """
    spans = []
    start = max(season.start, since) if since else season.start
    if start > season.end:
        return []
    while start <= season.end:
        end = min(start + timedelta(days=days - 1), season.end)
        spans.append((start, end))
        start = end + timedelta(days=1)
    return spans


def _paged_by_date(
    client: httpx.Client, path: str, season: Season, since: date | None = None, **params: Any
) -> list[dict[str, Any]]:
    """Every record for a season, a date window at a time.

    A window that comes back exactly at the limit was truncated, so it is split
    and both halves are retried. A single day at the limit cannot be split any
    further and is reported rather than silently accepted.
    """
    pending = list(reversed(_windows(season, since=since)))
    collected: list[dict[str, Any]] = []

    while pending:
        start, end = pending.pop()
        payload = _get(
            client,
            path,
            season=season.year,
            startDateRange=start.isoformat(),
            endDateRange=end.isoformat(),
            **params,
        )
        batch = payload or []

        if len(batch) >= PAGE_LIMIT:
            if start == end:
                log.error(
                    "%s: %s alone returns the %s record limit. Some of that day is "
                    "unreachable by date and needs another filter.",
                    path,
                    start,
                    PAGE_LIMIT,
                )
            else:
                middle = start + timedelta(days=(end - start).days // 2)
                log.info(
                    "%s: %s to %s hit the limit; splitting at %s", path, start, end, middle
                )
                pending.append((middle + timedelta(days=1), end))
                pending.append((start, middle))
                continue

        collected.extend(batch)

    return collected


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
        # A cancelled or postponed fixture comes back with both scores set to
        # 0 rather than null, so "both scores are present" was enough to
        # promote one to completed. A basketball game cannot end 0-0, and an
        # imaginary tie entered Elo as a real result between two teams that
        # never played.
        "is_completed": (
            status in ("final", "completed", "post")
            or (home_score is not None and away_score is not None)
        )
        and bool((home_score or 0) + (away_score or 0)),
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


def extract_games(
    seasons: list[Season], since: date | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Games in each requested season, paged past the record limit.

    A bare season request returns 3,000 games and stops in early January, so
    the season is walked in date windows. Deduping on game_id makes the window
    boundaries harmless. `since` limits the walk to recent dates for a daily
    run; the loader upserts on game_id, so a partial extract corrects the games
    it covers and leaves the rest of the season alone.
    """
    rows: dict[str, dict[str, Any]] = {}
    failed = 0

    with _client() as client:
        for season in seasons:
            try:
                payload = _paged_by_date(client, "/games", season, since=since)
            except (httpx.HTTPStatusError, RuntimeError) as exc:
                failed += 1
                log.error("Skipping games for %s: %s", season.label, exc)
                continue

            found = 0
            for game in payload:
                parsed = parse_game(game, season.year)
                if parsed:
                    rows[parsed["game_id"]] = parsed
                    found += 1
            log.info("CBD %s: %s games", season.label, found)

    _require_a_season("games", seasons, failed)
    return {"ncaa_games": list(rows.values())}


# --------------------------------------------------------------------------
# Team box scores
# --------------------------------------------------------------------------

# CBD nests the counting stats: `fieldGoals` is an object with made,
# attempted, and pct rather than three flat keys. This maps each warehouse
# column to the object and the key inside it. A stat that is a plain number
# names no inner key.
BOX_FIELDS: dict[str, tuple[str, str | None]] = {
    "field_goals_made": ("fieldGoals", "made"),
    "field_goals_attempted": ("fieldGoals", "attempted"),
    "three_pointers_made": ("threePointFieldGoals", "made"),
    "three_pointers_attempted": ("threePointFieldGoals", "attempted"),
    "two_pointers_made": ("twoPointFieldGoals", "made"),
    "two_pointers_attempted": ("twoPointFieldGoals", "attempted"),
    "free_throws_made": ("freeThrows", "made"),
    "free_throws_attempted": ("freeThrows", "attempted"),
    "rebounds": ("rebounds", "total"),
    "offensive_rebounds": ("rebounds", "offensive"),
    "defensive_rebounds": ("rebounds", "defensive"),
    "turnovers": ("turnovers", "total"),
    "fouls": ("fouls", "total"),
    "points": ("points", "total"),
    "assists": ("assists", None),
    "steals": ("steals", None),
    "blocks": ("blocks", None),
    "possessions": ("possessions", None),
}


def _stat(stats: dict[str, Any], group: str, key: str | None) -> Any:
    """One counting stat, whether it is nested or flat."""
    value = stats.get(group)
    if isinstance(value, dict):
        return value.get(key) if key else None
    return value if key is None else None


def parse_team_box(entry: dict[str, Any], season_year: int) -> list[dict[str, Any]]:
    """One row from one `/games/teams` record.

    Each record is a single team's line in a single game, with its own stats
    under `teamStats` and the opponent's under `opponentStats`. The opponent
    gets its own record elsewhere in the feed, so this emits one row, not two.
    """
    game_id = _first(entry, "gameId", "id")
    team_id = _first(entry, "teamId")
    if game_id is None or team_id is None:
        return []

    stats = entry.get("teamStats")
    if not isinstance(stats, dict):
        return []

    row: dict[str, Any] = {
        "season": season_year,
        "game_id": str(game_id),
        "team_id": str(team_id),
        "team_name": _first(entry, "team", "school", "teamName"),
        "opponent_id": str(_first(entry, "opponentId") or "") or None,
        "is_home": entry.get("isHome"),
        "extracted_at": datetime.now(UTC),
    }
    for column, (group, key) in BOX_FIELDS.items():
        row[column] = _to_int(_stat(stats, group, key))

    return [row]


def _conferences(client: httpx.Client, season: Season) -> list[str]:
    """Every conference in a season, read off the team dimension."""
    payload = _get(client, "/teams", season=season.year)
    names = {
        str(_first(team, "conference", "conferenceName") or "").strip()
        for team in payload or []
    }
    return sorted(name for name in names if name)


def extract_box_scores(seasons: list[Season]) -> dict[str, list[dict[str, Any]]]:
    """Team box score lines, paged by conference.

    Unlike /games, this endpoint ignores the date range parameters: a November
    window comes back at the same 3,000 record limit as the whole season. It
    does honour `conference`, so the season is walked one league at a time and
    deduped, since a non-conference game is returned under both teams' leagues.
    """
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    failed = 0

    with _client() as client:
        for season in seasons:
            try:
                conferences = _conferences(client, season)
            except (httpx.HTTPStatusError, RuntimeError) as exc:
                failed += 1
                log.error("Skipping box scores for %s: %s", season.label, exc)
                continue

            before = len(rows)
            lost = 0
            for conference in conferences:
                try:
                    payload = _get(
                        client, "/games/teams", season=season.year, conference=conference
                    )
                except (httpx.HTTPStatusError, RuntimeError) as exc:
                    lost += 1
                    log.error("Box scores for %s %s: %s", season.label, conference, exc)
                    continue

                batch = payload or []
                if len(batch) >= PAGE_LIMIT:
                    log.error(
                        "%s %s returned the %s record limit; that league is truncated.",
                        season.label,
                        conference,
                        PAGE_LIMIT,
                    )

                for entry in batch:
                    for row in parse_team_box(entry, season.year):
                        rows[(row["game_id"], row["team_id"])] = row

            # A season whose every league was refused is a lost season, not a
            # thin one, and counts the same as one that never got a conference
            # list at all.
            if conferences and lost == len(conferences):
                failed += 1

            log.info(
                "CBD %s: %s box score lines across %s conferences",
                season.label,
                len(rows) - before,
                len(conferences),
            )

    _require_a_season("box scores", seasons, failed)
    return {"ncaa_team_box": list(rows.values())}


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


def extract_lines(
    seasons: list[Season], since: date | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Closing betting lines, the benchmark the predictor is measured against."""
    rows: list[dict[str, Any]] = []
    failed = 0

    with _client() as client:
        for season in seasons:
            try:
                payload = _paged_by_date(client, "/lines", season, since=since)
            except (httpx.HTTPStatusError, RuntimeError) as exc:
                failed += 1
                log.error("Skipping lines for %s: %s", season.label, exc)
                continue

            season_rows = [
                row for entry in payload for row in parse_lines(entry, season.year)
            ]
            rows.extend(season_rows)
            log.info("CBD %s: %s betting lines", season.label, len(season_rows))

    _require_a_season("betting lines", seasons, failed)
    return {"ncaa_betting_lines": rows}


# --------------------------------------------------------------------------
# Ratings
# --------------------------------------------------------------------------
#
# This replaced Barttorvik's T-Rank export. That source is refused at the CDN
# edge for requests from a data centre: `ingest diagnose` shows CloudFront
# returning 403 to a GitHub Actions runner under any User-Agent, so a scheduled
# pipeline could never read it. CBD serves adjusted efficiency itself, keyed on
# the same team id as every other table here, which also removes the name
# crosswalk the old join needed.

# The four factors, and where the "allowed" half of each pair comes from. A
# team's defensive four factors are its opponents' offensive ones.
FOUR_FACTORS = {
    "efg_pct": "effectiveFieldGoalPct",
    "turnover_pct": "turnoverRatio",
    "off_reb_pct": "offensiveReboundPct",
    "ft_rate": "freeThrowRate",
}


def _season_stats(client: httpx.Client, season: Season) -> dict[str, dict[str, Any]]:
    """Tempo, record, and four factors per team, keyed by team id.

    /ratings/adjusted carries the efficiency numbers and nothing else, so the
    tempo the prediction needs and the shooting splits the dashboard shows come
    from the season stats endpoint alongside it.
    """
    payload = _get(client, "/stats/team/season", season=season.year)
    stats: dict[str, dict[str, Any]] = {}

    for entry in payload or []:
        team_id = _first(entry, "teamId")
        if team_id is None:
            continue

        team = entry.get("teamStats") or {}
        opponent = entry.get("opponentStats") or {}
        team_factors = team.get("fourFactors") or {}
        opponent_factors = opponent.get("fourFactors") or {}

        row: dict[str, Any] = {
            "wins": _to_float(_first(entry, "wins")),
            "losses": _to_float(_first(entry, "losses")),
            "games": _to_float(_first(entry, "games")),
            "adj_tempo": _to_float(_first(entry, "pace")),
            "two_pt_pct": _to_float(_stat(team, "twoPointFieldGoals", "pct")),
            "two_pt_pct_allowed": _to_float(_stat(opponent, "twoPointFieldGoals", "pct")),
            "three_pt_pct": _to_float(_stat(team, "threePointFieldGoals", "pct")),
            "three_pt_pct_allowed": _to_float(_stat(opponent, "threePointFieldGoals", "pct")),
        }
        for column, key in FOUR_FACTORS.items():
            row[column] = _to_float(team_factors.get(key))
            row[f"{column}_allowed" if column != "turnover_pct" else "turnover_pct_forced"] = (
                _to_float(opponent_factors.get(key))
            )

        stats[str(team_id)] = row

    return stats


def parse_rating(
    entry: dict[str, Any], stats: dict[str, dict[str, Any]], season_year: int, snapshot: date
) -> dict[str, Any] | None:
    team_id = _first(entry, "teamId")
    if team_id is None:
        return None

    offensive = _to_float(_first(entry, "offensiveRating"))
    defensive = _to_float(_first(entry, "defensiveRating"))
    net = _to_float(_first(entry, "netRating"))

    row: dict[str, Any] = {
        "snapshot_date": snapshot,
        "season": season_year,
        "team_id": str(team_id),
        "team_name": _first(entry, "team", "school", "teamName"),
        "conference": _first(entry, "conference"),
        "adj_oe": offensive,
        "adj_de": defensive,
        # CBD publishes the margin directly. Preferring it to a subtraction
        # keeps this consistent with the rankings on the same record.
        "adj_margin": net if net is not None else _subtract(offensive, defensive),
        "extracted_at": datetime.now(UTC),
    }

    blank = dict.fromkeys(
        (
            "wins", "losses", "games", "adj_tempo",
            "efg_pct", "efg_pct_allowed", "turnover_pct", "turnover_pct_forced",
            "off_reb_pct", "off_reb_pct_allowed", "ft_rate", "ft_rate_allowed",
            "two_pt_pct", "two_pt_pct_allowed", "three_pt_pct", "three_pt_pct_allowed",
        )
    )
    row.update(blank | stats.get(str(team_id), {}))
    return row


def _subtract(left: float | None, right: float | None) -> float | None:
    return None if left is None or right is None else left - right


def extract_ratings(
    seasons: list[Season], snapshot: date | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Adjusted efficiency for every requested season, keyed by team id."""
    snapshot = snapshot or utc_today()
    rows: list[dict[str, Any]] = []
    failed = 0

    with _client() as client:
        for season in seasons:
            try:
                payload = _get(client, "/ratings/adjusted", season=season.year)
                stats = _season_stats(client, season)
            except (httpx.HTTPStatusError, RuntimeError) as exc:
                failed += 1
                log.error("Skipping ratings for %s: %s", season.label, exc)
                continue

            season_rows = [
                parsed
                for entry in payload or []
                if (parsed := parse_rating(entry, stats, season.year, snapshot))
            ]
            rows.extend(season_rows)
            log.info(
                "CBD %s: %s rated teams, %s with season stats",
                season.label,
                len(season_rows),
                sum(1 for row in season_rows if row["adj_tempo"] is not None),
            )

    _require_a_season("ratings", seasons, failed)
    return {"ncaa_ratings": rows}
