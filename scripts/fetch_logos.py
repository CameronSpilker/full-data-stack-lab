#!/usr/bin/env python
"""Mirror each team's logo into the dashboard's static files.

The warehouse carries `team_logo_url`, which is wherever the source publishes
the image. Pointing the pages straight at that URL would work until it did
not: it is a third-party host the site does not control, and a logo that
stops resolving puts a broken image beside every number on the page. So the
files are mirrored here and served from the dashboard's own origin.

The contract the pages rely on is one rule rather than a lookup table:

    a team with a mirrored logo has it at /logos/<team_id>.png

Nothing reads the manifest at build time. It is written for auditing: which
teams resolved, from where, and how big the file was. A team with no logo is
ordinary rather than an error, and every page that draws one falls back to the
team's initials, so a partial mirror degrades a page instead of breaking it.

Only PNG is saved under that path. A source serving anything else is saved
under its real extension and reported as a miss, because a JPEG written to a
.png path is a lie the browser forgives and the next reader does not.

    python scripts/fetch_logos.py                # every team missing a file
    python scripts/fetch_logos.py --force        # re-fetch teams already saved
    python scripts/fetch_logos.py --limit 10     # a sample, for a first look

Needs network access to whatever host the source names. It is deliberately not
part of the nightly pipeline: a team's logo changes about as often as its
name, and re-fetching 360 images every night to find that out would be rude to
the host and slow for no gain. Run it after a backfill rebuilds the team
dimension, or when a page shows initials where a logo belongs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

import duckdb
import httpx

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_WAREHOUSE = REPO_ROOT / "data" / "warehouse.duckdb"
DEFAULT_OUT = REPO_ROOT / "dashboard" / "static" / "logos"

USER_AGENT = "full-data-stack-lab (+https://github.com/CameronSpilker/full-data-stack-lab)"

# One request per team, and nobody is waiting on this. A pause between them
# keeps a 360-image run from looking like something the host should throttle.
REQUEST_DELAY_SECONDS = 0.25
TIMEOUT_SECONDS = 20
ATTEMPTS = 3

# Read from the bytes rather than trusted from the URL or the content-type
# header: a CDN that serves an HTML error page with a 200 and a .png path is
# the exact case that puts a file full of markup where a logo should be.
MAGIC = {
    b"\x89PNG\r\n\x1a\n": ".png",
    b"\xff\xd8\xff": ".jpg",
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
    b"RIFF": ".webp",
}

TEAMS_SQL = """
select distinct on (team_id)
    team_id,
    team_name,
    team_logo_url
from marts.mart_team_season
where team_logo_url is not null
order by team_id, season desc
"""


def detect_extension(payload: bytes) -> str | None:
    """The real format of these bytes, or None if it is not an image at all."""
    if payload.lstrip()[:5].lower() in (b"<html", b"<!doc"):
        return None
    for signature, extension in MAGIC.items():
        if payload.startswith(signature):
            # WEBP is RIFF with a marker four bytes later; RIFF alone is any
            # container, including audio.
            if signature == b"RIFF" and payload[8:12] != b"WEBP":
                continue
            return extension
    if payload.lstrip()[:5].lower() == b"<svg " or b"<svg" in payload[:200].lower():
        return ".svg"
    return None


def fetch(client: httpx.Client, url: str) -> bytes:
    """Get one logo, retrying a transient failure a couple of times."""
    last: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            response = client.get(url)
            response.raise_for_status()
            return response.content
        except (httpx.HTTPError, httpx.StreamError) as error:
            last = error
            if attempt < ATTEMPTS:
                time.sleep(2**attempt * 0.5)
    raise RuntimeError(f"{url}: {last}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--warehouse",
        type=pathlib.Path,
        default=DEFAULT_WAREHOUSE,
        help="DuckDB file to read the team dimension from.",
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=DEFAULT_OUT,
        help="Directory to mirror into. Served by the dashboard at /logos.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch teams whose file is already on disk.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Stop after this many teams. For a first look, not for a real run.",
    )
    args = parser.parse_args()

    if not args.warehouse.exists():
        print(f"No warehouse at {args.warehouse}.", file=sys.stderr)
        print(
            "Build one with `ingest demo` and a dbt build, or fetch the "
            "published copy named in charts/README.md.",
            file=sys.stderr,
        )
        return 1

    with duckdb.connect(str(args.warehouse), read_only=True) as connection:
        teams = connection.execute(TEAMS_SQL).fetchall()

    if not teams:
        # The synthetic demo seasons carry no logos at all, which is the usual
        # reason to land here. It is not a failure: there is simply nothing to
        # mirror, and every page already draws initials in that case.
        print("No team in this warehouse has a logo URL. Nothing to fetch.")
        return 0

    if args.limit:
        teams = teams[: args.limit]

    args.out.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, dict[str, object]] = {}
    manifest_path = args.out / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())

    saved = skipped = failed = 0

    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        for team_id, team_name, url in teams:
            target = args.out / f"{team_id}.png"

            if target.exists() and not args.force:
                skipped += 1
                continue

            try:
                payload = fetch(client, url)
            except RuntimeError as error:
                print(f"  MISS {team_name}: {error}", file=sys.stderr)
                failed += 1
                continue
            finally:
                time.sleep(REQUEST_DELAY_SECONDS)

            extension = detect_extension(payload)
            if extension is None:
                print(
                    f"  MISS {team_name}: {url} did not return an image "
                    f"({len(payload)} bytes)",
                    file=sys.stderr,
                )
                failed += 1
                continue

            if extension != ".png":
                # Saved under its real extension so the bytes are not lost,
                # and reported, because the pages will still draw initials
                # for this team until it is a PNG at the conventional path.
                other = args.out / f"{team_id}{extension}"
                other.write_bytes(payload)
                print(
                    f"  MISS {team_name}: served {extension}, saved as "
                    f"{other.name}. The page draws initials until it is a PNG.",
                    file=sys.stderr,
                )
                failed += 1
                continue

            target.write_bytes(payload)
            manifest[str(team_id)] = {
                "team_name": team_name,
                "path": f"/logos/{team_id}.png",
                "source": url,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            saved += 1
            print(f"  {team_name} -> {target.name} ({len(payload):,} bytes)")

    manifest_path.write_text(json.dumps(dict(sorted(manifest.items())), indent=2) + "\n")

    print(
        f"\n{saved} saved, {skipped} already on disk, {failed} without a usable "
        f"image, out of {len(teams)} teams with a logo URL."
    )
    # Relative when it sits in the repo, absolute when --out pointed
    # somewhere else. relative_to raises rather than falling back on its own.
    try:
        where = manifest_path.relative_to(REPO_ROOT)
    except ValueError:
        where = manifest_path
    print(f"Manifest: {where}")

    # A run that reached no team at all is a broken run rather than a quiet
    # one, and should not report success to whatever called it.
    return 1 if saved == 0 and skipped == 0 and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
