#!/usr/bin/env python
"""Mirror team logos from the sports-assets Polymarket archive.

The third source for dashboard/static/logos, after scripts/fetch_logos.py
(empty until the warehouse carries `team_logo_url`) and
scripts/import_npm_logos.mjs (forty programs, drawn from vector art). This
one covers the rest of Division I.

The npm package `sports-assets-archive-polymarket-team-logos-2` (MIT) is a
snapshot of the team images Polymarket serves for its college basketball
markets, with an index of where each file came from. Its `cbb` league holds
some 1,300 schools across every division, which covers every team in
mart_team_season.

Teams are matched by name. Most names agree once case, punctuation and
"State"/"Saint" are normalised; the rest are in OVERRIDES, each checked by
eye against a contact sheet. A team whose image is shared with another team
is skipped rather than given it, because a shared image there is the source's
placeholder, not a logo.

Each image is drawn into a 256px transparent square, the same as the npm
logos, and saved with a 256-colour palette. Some sources are JPEG-like RGB on a white field; that field is made
transparent from the corners inwards, so the logo sits on the page rather
than in a white box.

Existing files are left alone unless --force is given, so the forty vector
logos stay. Needs Pillow and duckdb:

    mkdir -p /tmp/logos && cd /tmp/logos && curl -fsSLO \\
      https://registry.npmjs.org/sports-assets-archive-polymarket-team-logos-2/-/sports-assets-archive-polymarket-team-logos-2-0.1.0.tgz
    tar xzf sports-assets-archive-polymarket-team-logos-2-0.1.0.tgz
    pip install pillow
    python scripts/import_archive_logos.py /tmp/logos/package
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import pathlib
import re
import sys

import duckdb
from PIL import Image, ImageDraw

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_WAREHOUSE = REPO_ROOT / "data" / "warehouse.duckdb"
DEFAULT_OUT = REPO_ROOT / "dashboard" / "static" / "logos"

PACKAGE = "sports-assets-archive-polymarket-team-logos-2@0.1.0"
LEAGUE = "cbb"
SIZE = 256
PADDING = 12

# Warehouse team id -> the archive's label, where the names do not agree.
OVERRIDES = {
    "8": "American Eagles",
    "9": "Appalachian State Mountaineers",
    "27": "Boston Terriers",
    "36": "Bakersfield Roadrunners",
    "38": "CSUN Matadors",
    "44": "Central Connecticut State Blue Devils",
    "66": "Delaware Fightin' Blue Hens",
    "69": "Detroit Titans",
    "82": "Evansville Aces",
    "89": "Florida International Golden Panthers",
    "103": "Grambling State Tigers",
    "104": "Grand Canyon Antelopes",
    "115": "IU Indy Jaguars",
    "146": "LIU Sharks",
    "148": "Louisiana-Lafayette Ragin' Cajuns",
    "162": "McNeese State Cowboys",
    "166": "Merrimack College Warriors",
    "185": "North Carolina State Wolfpack",
    "227": "Penn Quakers",
    "246": "Southeastern Louisiana Lions",
    "247": "SIUE Cougars",
    "260": "San Jose State Spartans",
    "262": "Seattle Redhawks",
    "268": "USC Upstate Spartans",
    "280": "St. Thomas (MN) Tommies",
    "306": "Albany Great Danes",
    "310": "California-San Diego Tritons",
    "314": "Connecticut Huskies",
    "316": "Louisiana-Monroe Warhawks",
    "318": "Massachusetts-Lowell River Hawks",
    "320": "UNCG Spartans",
    "321": "UNCW Seahawks",
    "322": "UNLV Runnin' Rebels",
    "326": "Texas-Rio Grande Valley Vaqueros",
    "362": "Queens (NC) Royals",
}

TEAMS_SQL = """
select distinct on (team_id) team_id, team_name
from marts.mart_team_season
order by team_id, season desc
"""


def normalise(name: str) -> str:
    name = name.lower().replace("&", "and").replace("saint", "st").replace("state", "st")
    return re.sub(r"[^a-z0-9]", "", name)


def clear_white_field(image: Image.Image) -> Image.Image:
    """Make a white background transparent, working in from the corners.

    Only pixels connected to a near-white corner are cleared, so white inside
    the logo (a letter's counter, a stripe) is kept.
    """
    image = image.convert("RGBA")
    width, height = image.size
    for corner in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        r, g, b, a = image.getpixel(corner)
        if a and min(r, g, b) >= 235:
            ImageDraw.floodfill(image, corner, (255, 255, 255, 0), thresh=40)
    return image


def to_square_png(path: pathlib.Path) -> bytes:
    image = Image.open(path)
    if image.mode != "RGBA" or image.getextrema()[3][0] == 255:
        image = clear_white_field(image)
    image = image.convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    if bbox:
        image = image.crop(bbox)
    # Scaled to fit both ways. A few sources are only 70px across, and a
    # crest never draws a logo wider than about 80px, so growing those costs
    # nothing a reader would see; leaving them small would draw a speck.
    inner = SIZE - 2 * PADDING
    scale = inner / max(image.size)
    image = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.LANCZOS,
    )
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(image, ((SIZE - image.width) // 2, (SIZE - image.height) // 2), image)
    # A 256-colour palette with alpha. Side by side with the full-colour
    # file it is indistinguishable at crest size, and it is a fifth of the
    # bytes, which every page that draws a crest has to download.
    canvas = canvas.quantize(256, method=Image.Quantize.FASTOCTREE)
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("package", type=pathlib.Path, help="The unpacked package/ directory.")
    parser.add_argument("--warehouse", type=pathlib.Path, default=DEFAULT_WAREHOUSE)
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true", help="Replace files already on disk.")
    args = parser.parse_args()

    index = json.loads((args.package / "archive" / "polymarket" / "index.json").read_text())
    entries = [e for e in index["entries"] if e["sourceLeagueId"] == LEAGUE]
    by_label = {e["label"]: e for e in entries}
    by_normal: dict[str, list[dict]] = collections.defaultdict(list)
    for entry in entries:
        by_normal[normalise(entry["label"])].append(entry)
    shared = collections.Counter(e["sha256"] for e in entries)

    with duckdb.connect(str(args.warehouse), read_only=True) as connection:
        teams = connection.execute(TEAMS_SQL).fetchall()

    manifest_path = args.out / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    written = skipped = 0

    for team_id, team_name in teams:
        target = args.out / f"{team_id}.png"
        if target.exists() and not args.force:
            skipped += 1
            continue

        if team_id in OVERRIDES:
            entry = by_label.get(OVERRIDES[team_id])
        elif team_name in by_label:
            entry = by_label[team_name]
        else:
            candidates = by_normal.get(normalise(team_name), [])
            entry = candidates[0] if len(candidates) == 1 else None

        if entry is None:
            print(f"  MISS {team_name}: no match in the archive; add it to OVERRIDES", file=sys.stderr)
            continue
        if shared[entry["sha256"]] > 1:
            print(f"  MISS {team_name}: {entry['label']} is the archive's placeholder", file=sys.stderr)
            continue

        png = to_square_png(args.package / entry["file"])
        target.write_bytes(png)
        manifest[team_id] = {
            "team_name": team_name,
            "path": f"/logos/{team_id}.png",
            "source": f"npm:{PACKAGE}/{entry['file']} ({entry['originalUrl']})",
            "bytes": len(png),
            "sha256": hashlib.sha256(png).hexdigest(),
        }
        written += 1

    ordered = dict(sorted(manifest.items(), key=lambda item: int(item[0])))
    manifest_path.write_text(json.dumps(ordered, indent=2) + "\n")
    print(f"Wrote {written} logos; {skipped} teams already had one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
