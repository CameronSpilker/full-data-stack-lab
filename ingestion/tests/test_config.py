from ingestion.config import Tool, load_tools


def test_registry_loads_and_is_consistent():
    tools = load_tools()

    assert tools, "the registry should not be empty"
    assert len({tool.name for tool in tools}) == len(tools), "tool names must be unique"
    assert len({tool.repo for tool in tools}) == len(tools), "repos must be unique"


def test_every_tool_has_a_known_category():
    allowed = {"transformation", "orchestration", "ingestion", "storage", "bi"}

    # Categories drive the accepted_values test on the marts, so an unknown
    # value here would fail dbt rather than this test. Catch it earlier.
    for tool in load_tools():
        assert tool.category in allowed, f"{tool.name} has category {tool.category!r}"


def test_repo_is_split_into_owner_and_name():
    tool = Tool(name="dbt", repo="dbt-labs/dbt-core", pypi="dbt-core", category="transformation")

    assert tool.owner == "dbt-labs"
    assert tool.repo_name == "dbt-core"
