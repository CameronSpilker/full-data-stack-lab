#!/usr/bin/env python
"""Derive each team's second colour from its logo, into a dbt seed.

The warehouse carries one colour per team (`team_color`, from the source).
One is not enough to tell two teams apart when their colours are the same
navy, which is BYU against Michigan, the matchup the boards feature. Every
team now has a logo in dashboard/static/logos, and a logo is the school's
own statement of its colours, so the second colour is read from it.

For each logo, the opaque pixels are reduced to a few colours, and the
second colour is the most common one that is neither near-white (a logo's
outline or background) nor too close to the team's primary colour to tell
apart from it. A team where no such colour exists gets none, and the marts
fall back from there.

    python scripts/derive_team_colors.py

Writes transform/seeds/team_secondary_colors.csv. Re-run it when logos
change; it is deterministic for the same files.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib

import duckdb
from PIL import Image

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_WAREHOUSE = REPO_ROOT / "data" / "warehouse.duckdb"
LOGOS = REPO_ROOT / "dashboard" / "static" / "logos"
SEED = REPO_ROOT / "transform" / "seeds" / "team_secondary_colors.csv"

# Distance in OKLab, times 100. Below this two colours read as the same one
# at the size of a bar or a ring.
MIN_DISTANCE = 18
# A colour must cover this share of the logo's opaque pixels to count, so a
# thin trim line does not become a team's colour.
MIN_SHARE = 0.04


def oklab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    def linear(channel: int) -> float:
        c = channel / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(c) for c in rgb)
    l_ = math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m_ = math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s_ = math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return 100 * math.dist(oklab(a), oklab(b))


def from_hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def secondary(logo: pathlib.Path, primary: tuple[int, int, int] | None) -> str | None:
    image = Image.open(logo).convert("RGBA")
    pixels = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
    opaque = [(r, g, b) for r, g, b, a in pixels if a >= 200]
    if not opaque:
        return None
    swatch = Image.new("RGB", (len(opaque), 1))
    swatch.putdata(opaque)
    reduced = swatch.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
    palette = reduced.getpalette()
    counts = sorted(reduced.getcolors(), reverse=True)
    for count, index in counts:
        if count / len(opaque) < MIN_SHARE:
            break
        rgb = tuple(palette[index * 3 : index * 3 + 3])
        if min(rgb) >= 225:
            continue
        if primary is not None and distance(rgb, primary) < MIN_DISTANCE:
            continue
        return "{:02x}{:02x}{:02x}".format(*rgb)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--warehouse", type=pathlib.Path, default=DEFAULT_WAREHOUSE)
    args = parser.parse_args()

    with duckdb.connect(str(args.warehouse), read_only=True) as connection:
        primaries = dict(
            connection.execute(
                "select distinct on (team_id) team_id, team_color "
                "from marts.mart_team_season order by team_id, season desc"
            ).fetchall()
        )

    manifest = json.loads((LOGOS / "manifest.json").read_text())
    rows = []
    for team_id in sorted(manifest, key=int):
        logo = LOGOS / f"{team_id}.png"
        if not logo.exists():
            continue
        primary = primaries.get(team_id)
        color = secondary(logo, from_hex(primary) if primary else None)
        if color:
            rows.append((team_id, color))

    with SEED.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["team_id", "team_secondary_color"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} secondary colours to {SEED.relative_to(REPO_ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
