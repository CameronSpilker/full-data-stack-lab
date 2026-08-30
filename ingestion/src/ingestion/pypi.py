"""Extract Python package download counts from the public pypistats API.

pypistats reports the trailing 180 days of daily downloads per package, so
unlike the GitHub extractors this one carries real history on every run and
the loader deduplicates on (package, download_date).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, date, datetime
from typing import Any

import httpx

from .config import Tool, utc_today

log = logging.getLogger(__name__)

API = "https://pypistats.org/api"
USER_AGENT = "full-data-stack-lab (+https://github.com/CameronSpilker/full-data-stack-lab)"


def _client() -> httpx.Client:
    return httpx.Client(base_url=API, headers={"User-Agent": USER_AGENT}, timeout=30.0)


def fetch_overall(client: httpx.Client, tool: Tool, snapshot: date) -> list[dict[str, Any]]:
    """Daily download counts, excluding mirror traffic."""
    for attempt in range(4):
        response = client.get(f"/packages/{tool.pypi}/overall")
        if response.status_code == 429 or response.status_code >= 500:
            backoff = 2**attempt
            log.warning(
                "pypistats %s for %s; retrying in %ss",
                response.status_code,
                tool.pypi,
                backoff,
            )
            time.sleep(backoff)
            continue
        response.raise_for_status()
        break
    else:
        raise RuntimeError(f"pypistats request failed after retries: {tool.pypi}")

    extracted_at = datetime.now(UTC)
    return [
        {
            "snapshot_date": snapshot,
            "tool_name": tool.name,
            "package_name": tool.pypi,
            "download_date": row["date"],
            "category": row["category"],
            "downloads": row["downloads"],
            "extracted_at": extracted_at,
        }
        for row in response.json()["data"]
        if row["category"] == "without_mirrors"
    ]


def extract(tools: list[Tool], snapshot: date | None = None) -> dict[str, list[dict[str, Any]]]:
    """Run the PyPI extractor over every tool that publishes a package."""
    snapshot = snapshot or utc_today()
    rows: list[dict[str, Any]] = []

    with _client() as client:
        for tool in tools:
            if not tool.pypi:
                continue
            try:
                rows.extend(fetch_overall(client, tool, snapshot))
                log.info("Extracted %s", tool.pypi)
            except httpx.HTTPStatusError as exc:
                log.error("Skipping %s: %s", tool.pypi, exc)

    return {"pypi_downloads": rows}
