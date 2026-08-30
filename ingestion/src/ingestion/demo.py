"""Deterministic synthetic extracts, for development and CI.

The real extractors need network access to api.github.com and pypistats.org.
This module fabricates the same table shapes so `dbt build`, the Dagster
graph, and the Evidence dashboard can all run end to end on a clean checkout
with no network and no API budget.

The numbers here are INVENTED. Nothing produced by this module should ever be
published as a finding about a real project — it exists to exercise the
pipeline, not to describe the ecosystem.
"""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta
from typing import Any

from .config import Tool, utc_today

SEED = 20260830
SNAPSHOT_COUNT = 12  # weekly snapshots of history
LICENSES = ["Apache-2.0", "MIT", "BSD-3-Clause"]
LANGUAGES = ["Python", "TypeScript", "Go", "Java", "C++", "Rust"]


def _snapshots(through: date, count: int = SNAPSHOT_COUNT) -> list[date]:
    """Weekly snapshot dates, oldest first, ending on `through`."""
    return [through - timedelta(weeks=offset) for offset in reversed(range(count))]


def extract(tools: list[Tool], snapshot: date | None = None) -> dict[str, list[dict[str, Any]]]:
    """Generate a full synthetic history for every tool in the registry."""
    through = snapshot or utc_today()
    rng = random.Random(SEED)
    extracted_at = datetime.now(UTC)

    repos: list[dict[str, Any]] = []
    contributors: list[dict[str, Any]] = []
    releases: list[dict[str, Any]] = []
    downloads: list[dict[str, Any]] = []

    for tool in tools:
        # Each tool gets a stable starting scale and growth rate.
        stars = rng.randint(2_000, 60_000)
        forks = int(stars * rng.uniform(0.08, 0.25))
        contributor_count = rng.randint(40, 900)
        weekly_growth = rng.uniform(0.002, 0.02)
        created_at = datetime(
            rng.randint(2012, 2021), rng.randint(1, 12), rng.randint(1, 28),
            tzinfo=UTC,
        )
        language = rng.choice(LANGUAGES)
        license_id = rng.choice(LICENSES)
        daily_downloads = rng.randint(5_000, 400_000) if tool.pypi else 0
        release_index = rng.randint(20, 300)

        for week, snapshot_date in enumerate(_snapshots(through)):
            stars = int(stars * (1 + weekly_growth))
            forks = int(forks * (1 + weekly_growth * 0.6))
            contributor_count += rng.randint(0, 4)

            repos.append(
                {
                    "snapshot_date": snapshot_date,
                    "tool_name": tool.name,
                    "repo_full_name": tool.repo,
                    "stars": stars,
                    "forks": forks,
                    "open_issues": rng.randint(50, 3_000),
                    "watchers": int(stars * 0.02),
                    "size_kb": rng.randint(10_000, 900_000),
                    "primary_language": language,
                    "license": license_id,
                    "created_at": created_at.isoformat(),
                    "pushed_at": (
                        datetime.combine(snapshot_date, datetime.min.time()).isoformat() + "Z"
                    ),
                    "extracted_at": extracted_at,
                }
            )

            contributors.append(
                {
                    "snapshot_date": snapshot_date,
                    "tool_name": tool.name,
                    "repo_full_name": tool.repo,
                    "contributor_count": contributor_count,
                    "extracted_at": extracted_at,
                }
            )

            # Roughly one release every other week.
            if week % 2 == 0:
                release_index += 1
                releases.append(
                    {
                        "snapshot_date": through,
                        "tool_name": tool.name,
                        "repo_full_name": tool.repo,
                        "release_tag": f"v1.{release_index}.0",
                        "release_name": f"{tool.name} 1.{release_index}.0",
                        "is_prerelease": rng.random() < 0.15,
                        "published_at": (
                            datetime.combine(snapshot_date, datetime.min.time()).isoformat() + "Z"
                        ),
                        "extracted_at": extracted_at,
                    }
                )

            if not tool.pypi:
                continue

            for day_offset in range(7):
                download_date = snapshot_date - timedelta(days=day_offset)
                if download_date > through:
                    continue
                weekend_dip = 0.55 if download_date.weekday() >= 5 else 1.0
                downloads.append(
                    {
                        "snapshot_date": through,
                        "tool_name": tool.name,
                        "package_name": tool.pypi,
                        "download_date": download_date.isoformat(),
                        "category": "without_mirrors",
                        "downloads": int(
                            daily_downloads * weekend_dip * rng.uniform(0.85, 1.15)
                        ),
                        "extracted_at": extracted_at,
                    }
                )

            daily_downloads = int(daily_downloads * (1 + weekly_growth))

    return {
        "github_repos": repos,
        "github_contributors": contributors,
        "github_releases": releases,
        "pypi_downloads": downloads,
    }
