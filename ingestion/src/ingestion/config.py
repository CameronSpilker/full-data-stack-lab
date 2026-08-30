"""Shared configuration: the tool registry and environment-driven paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# .../<repo>/ingestion/src/ingestion/config.py
_PKG = Path(__file__).resolve()
REPO_ROOT = _PKG.parents[3]
TOOLS_FILE = _PKG.parents[2] / "tools.yml"


@dataclass(frozen=True)
class Tool:
    name: str
    repo: str
    pypi: str | None
    category: str

    @property
    def owner(self) -> str:
        return self.repo.split("/", 1)[0]

    @property
    def repo_name(self) -> str:
        return self.repo.split("/", 1)[1]


def load_tools(path: Path | None = None) -> list[Tool]:
    """Read the tool registry from tools.yml."""
    source = path or TOOLS_FILE
    payload = yaml.safe_load(source.read_text())
    return [Tool(**entry) for entry in payload["tools"]]


def _resolve(value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def raw_data_dir() -> Path:
    path = _resolve(os.getenv("RAW_DATA_DIR", "data/raw"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def duckdb_path() -> Path:
    path = _resolve(os.getenv("DUCKDB_PATH", "data/warehouse.duckdb"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def github_token() -> str | None:
    """Optional. Without it the GitHub API allows 60 requests/hour."""
    return os.getenv("GITHUB_TOKEN") or None


def utc_today() -> date:
    """Today in UTC.

    Snapshot dates key the whole warehouse, so they must not depend on the
    timezone of whichever machine happens to run the pipeline.
    """
    return datetime.now(UTC).date()
