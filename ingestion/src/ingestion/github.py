"""Extract public repository metrics from the GitHub REST API.

Every extract is a dated snapshot: the API only reports current state, so
history is built by appending one row per repo per run. Nothing here needs
authentication, but a token raises the rate limit from 60 to 5,000 req/hour.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any

import httpx

from .config import Tool, github_token, utc_today

log = logging.getLogger(__name__)

API = "https://api.github.com"
USER_AGENT = "full-data-stack-lab (+https://github.com/CameronSpilker/full-data-stack-lab)"


def _client() -> httpx.Client:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    }
    token = github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        log.warning("No GITHUB_TOKEN set — limited to 60 requests/hour.")
    return httpx.Client(base_url=API, headers=headers, timeout=30.0)


def _get(client: httpx.Client, path: str, **params: Any) -> httpx.Response:
    """GET with retries, honouring GitHub's rate-limit reset header."""
    for attempt in range(5):
        response = client.get(path, params=params)

        if response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0":
            reset = int(response.headers.get("x-ratelimit-reset", "0"))
            wait = max(reset - time.time(), 0) + 1
            log.warning("Rate limited on %s; sleeping %.0fs", path, wait)
            time.sleep(wait)
            continue

        if response.status_code >= 500:
            backoff = 2**attempt
            log.warning("GitHub %s on %s; retrying in %ss", response.status_code, path, backoff)
            time.sleep(backoff)
            continue

        response.raise_for_status()
        return response

    raise RuntimeError(f"GitHub request failed after retries: {path}")


def fetch_repo(client: httpx.Client, tool: Tool, snapshot: date) -> dict[str, Any]:
    """One row of current repo state."""
    repo = _get(client, f"/repos/{tool.repo}").json()
    return {
        "snapshot_date": snapshot,
        "tool_name": tool.name,
        "repo_full_name": tool.repo,
        "stars": repo["stargazers_count"],
        "forks": repo["forks_count"],
        "open_issues": repo["open_issues_count"],
        "watchers": repo["subscribers_count"],
        "size_kb": repo["size"],
        "primary_language": repo.get("language"),
        "license": (repo.get("license") or {}).get("spdx_id"),
        "created_at": repo["created_at"],
        "pushed_at": repo["pushed_at"],
        "extracted_at": datetime.now(UTC),
    }


def fetch_contributors(client: httpx.Client, tool: Tool, snapshot: date) -> dict[str, Any]:
    """Contributor count, read from the last page of the paginated list.

    GitHub caps the contributor list at 500 for very large repos, so this is a
    floor rather than an exact count. The staging layer flags that.
    """
    response = _get(client, f"/repos/{tool.repo}/contributors", per_page=1, anon="false")
    link = response.headers.get("link", "")
    count = len(response.json())

    for part in link.split(","):
        if 'rel="last"' in part and "page=" in part:
            count = int(part.split("page=")[1].split(">")[0].split("&")[0])
            break

    return {
        "snapshot_date": snapshot,
        "tool_name": tool.name,
        "repo_full_name": tool.repo,
        "contributor_count": count,
        "extracted_at": datetime.now(UTC),
    }


def fetch_releases(
    client: httpx.Client, tool: Tool, snapshot: date, limit: int = 100
) -> Iterator[dict[str, Any]]:
    """Recent releases, newest first."""
    releases = _get(client, f"/repos/{tool.repo}/releases", per_page=min(limit, 100)).json()
    for release in releases[:limit]:
        yield {
            "snapshot_date": snapshot,
            "tool_name": tool.name,
            "repo_full_name": tool.repo,
            "release_tag": release["tag_name"],
            "release_name": release.get("name"),
            "is_prerelease": release["prerelease"],
            "published_at": release.get("published_at"),
            "extracted_at": datetime.now(UTC),
        }


def extract(tools: list[Tool], snapshot: date | None = None) -> dict[str, list[dict[str, Any]]]:
    """Run every GitHub extractor over the tool registry.

    A failure on one repo is logged and skipped so a single bad response does
    not lose the whole run.
    """
    snapshot = snapshot or utc_today()
    tables: dict[str, list[dict[str, Any]]] = {
        "github_repos": [],
        "github_contributors": [],
        "github_releases": [],
    }

    with _client() as client:
        for tool in tools:
            try:
                tables["github_repos"].append(fetch_repo(client, tool, snapshot))
                tables["github_contributors"].append(fetch_contributors(client, tool, snapshot))
                tables["github_releases"].extend(fetch_releases(client, tool, snapshot))
                log.info("Extracted %s", tool.repo)
            except httpx.HTTPStatusError as exc:
                log.error("Skipping %s: %s", tool.repo, exc)

    return tables
