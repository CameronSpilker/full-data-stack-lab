"""Ask the live sources what they actually do, and print the answers.

`ingest preflight` reports that a source came back wrong. This reports *why*,
which is a different job: it reads the CBD OpenAPI spec to find the parameters
an endpoint really accepts, probes the ones that returned nothing, and shows
the raw status and body of a request that was refused outright.

Everything here is read-only. It writes no files, touches no warehouse, and
prints no credentials.

Run it when preflight fails and the cause is not obvious from the coverage
table alone.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from . import cbd
from .config import Season

log = logging.getLogger(__name__)

SPEC_URL = "https://api.collegebasketballdata.com/openapi.json"
ENDPOINTS = ("/games", "/games/teams", "/lines", "/teams")

# Barttorvik refused a request carrying the project's own User-Agent. The most
# common reason a static file server does that is bot filtering on the header
# itself, so the probe repeats the identical request as a browser would send
# it. If both are refused the block is on the address, not the header, and no
# amount of header tuning will fix it.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _rule(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def spec_parameters() -> dict[str, Any]:
    """The parameters CBD's own spec says each endpoint takes."""
    _rule("CBD OpenAPI spec: what these endpoints actually accept")

    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(SPEC_URL)
            response.raise_for_status()
            spec = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        print(f"  Could not read the spec: {exc}")
        return {}

    paths = spec.get("paths", {})
    for endpoint in ENDPOINTS:
        definition = paths.get(endpoint, {}).get("get")
        if not definition:
            print(f"\n  {endpoint:20} not in the spec")
            continue

        print(f"\n  {endpoint}")
        for param in definition.get("parameters", []):
            required = "required" if param.get("required") else "optional"
            schema = param.get("schema", {})
            kind = schema.get("type", "?")
            print(f"      {param.get('name', '?'):24} {required:9} {kind}")

    return paths


def games_shape(season: Season) -> None:
    """Is the 3,000 row count the whole season, or a cap?"""
    _rule(f"/games?season={season.year}: is 3,000 the season or a limit?")

    with cbd._client() as client:
        payload = cbd._get(client, "/games", season=season.year)

    rows = payload or []
    dates = sorted(str(g.get("startDate") or g.get("startDateTime") or "")[:10] for g in rows)
    dates = [d for d in dates if d]
    types: dict[str, int] = {}
    for game in rows:
        key = str(game.get("seasonType") or game.get("season_type") or "unknown")
        types[key] = types.get(key, 0) + 1

    print(f"\n  rows returned     {len(rows):,}")
    print(f"  earliest date     {dates[0] if dates else 'none'}")
    print(f"  latest date       {dates[-1] if dates else 'none'}")
    print("  season types      " + ", ".join(f"{k}={v:,}" for k, v in sorted(types.items())))
    print(
        "\n  A latest date in midseason, or a count that is exactly round, means\n"
        "  the response is truncated and the rest needs paging or narrowing."
    )


def box_scores(season: Season) -> None:
    """A bare season returns nothing. Find the narrowing this endpoint wants."""
    _rule(f"/games/teams?season={season.year}: which parameters return rows?")

    # Each attempt is the same endpoint with one more filter than the last.
    attempts: list[dict[str, Any]] = [
        {"season": season.year},
        {"season": season.year, "seasonType": "regular"},
        {"season": season.year, "conference": "ACC"},
        {"season": season.year, "startDateRange": f"{season.year - 1}-11-01",
         "endDateRange": f"{season.year - 1}-11-30"},
    ]

    with cbd._client() as client:
        for params in attempts:
            label = ", ".join(f"{k}={v}" for k, v in params.items())
            try:
                payload = cbd._get(client, "/games/teams", **params)
                count = len(payload or [])
                mark = "ROWS" if count else "empty"
                print(f"\n  {mark:6} {count:>7,}  {label}")
            except (httpx.HTTPError, RuntimeError, cbd.MissingApiKey) as exc:
                print(f"\n  ERROR           {label}\n         {type(exc).__name__}: {exc}")


def barttorvik(season: Season) -> None:
    """Is the 403 about the header, or about the address?"""
    _rule(f"barttorvik.com/trank.php?year={season.year}: header block or IP block?")

    for label, agent in (
        ("project User-Agent", "full-data-stack-lab (+https://github.com/CameronSpilker/full-data-stack-lab)"),
        ("browser User-Agent", BROWSER_UA),
    ):
        headers = {
            "User-Agent": agent,
            "Accept": "text/csv,text/plain,*/*",
            "Referer": "https://barttorvik.com/trank.php",
        }
        try:
            with httpx.Client(timeout=60.0, follow_redirects=True, headers=headers) as client:
                response = client.get(
                    "https://barttorvik.com/trank.php",
                    params={"year": season.year, "csv": 1},
                )
            body = response.text[:200].replace("\n", " | ")
            print(f"\n  {label}")
            print(f"      status  {response.status_code}")
            print(f"      server  {response.headers.get('server', 'unknown')}")
            print(f"      body    {body!r}")
        except httpx.HTTPError as exc:
            print(f"\n  {label}\n      {type(exc).__name__}: {exc}")

    print(
        "\n  Both refused means the block is on the address, not the header, and\n"
        "  a runner in a data centre will not get past it by pretending harder."
    )


def run(season: Season) -> int:
    print(f"\nDiagnosing the live sources against {season.label}. Nothing is written.")
    spec_parameters()
    try:
        games_shape(season)
        box_scores(season)
    except cbd.MissingApiKey as exc:
        print(f"\n  Skipping the CBD probes: {exc}")
    barttorvik(season)
    print("\nDone. Nothing above changed any data.\n")
    return 0
