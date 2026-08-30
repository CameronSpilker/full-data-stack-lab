from datetime import date

from ingestion import demo
from ingestion.config import load_tools

SNAPSHOT = date(2026, 8, 30)


def test_demo_generates_every_raw_table():
    tables = demo.extract(load_tools(), SNAPSHOT)

    assert set(tables) == {
        "github_repos",
        "github_contributors",
        "github_releases",
        "pypi_downloads",
    }
    assert all(rows for rows in tables.values())


def test_demo_is_deterministic():
    first = demo.extract(load_tools(), SNAPSHOT)
    second = demo.extract(load_tools(), SNAPSHOT)

    # The dashboard and CI both depend on this being stable run to run.
    assert [row["stars"] for row in first["github_repos"]] == [
        row["stars"] for row in second["github_repos"]
    ]


def test_stars_never_fall_week_over_week():
    # The dbt project fails a run on a >10% weekly drop. Synthetic data must
    # not trip that test, or CI is red for a reason that is not a real defect.
    rows = demo.extract(load_tools(), SNAPSHOT)["github_repos"]

    by_tool: dict[str, list[tuple[date, int]]] = {}
    for row in rows:
        by_tool.setdefault(row["tool_name"], []).append((row["snapshot_date"], row["stars"]))

    for tool_name, series in by_tool.items():
        series.sort()
        stars = [count for _, count in series]
        assert stars == sorted(stars), f"{tool_name} stars are not monotonic"


def test_pypi_rows_only_for_packaged_tools():
    tools = load_tools()
    packaged = {tool.name for tool in tools if tool.pypi}

    rows = demo.extract(tools, SNAPSHOT)["pypi_downloads"]

    assert {row["tool_name"] for row in rows} == packaged
