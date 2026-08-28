"""Integration tests for the osw-mcp server against a live OSL instance.

Excluded from the default run (tests/integration is ignored). Provide live
credentials to run:

    uv run pytest tests/integration/test_mcp_server.py -o addopts="" \
        --wiki_domain <domain> --wiki_username <user> --wiki_password <pass>

The wiki_* fixtures self-skip when credentials are absent.
"""

import pytest

import osw.service.ops  # noqa: F401  (registers the operations)
from osw.service import config
from osw.service.context import Context, Policy
from osw.service.registry import bind, iter_operations


@pytest.fixture
def mcp_tools(wiki_domain, wiki_username, wiki_password, tmp_path, monkeypatch):
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("OSW_MCP_ENV_FILE", str(empty))
    monkeypatch.setenv("OSW_DOMAIN", wiki_domain)
    monkeypatch.setenv("OSW_USERNAME", wiki_username)
    monkeypatch.setenv("OSW_PASSWORD", wiki_password)
    monkeypatch.setenv("OSW_MCP_STATE_DIR", str(tmp_path / "state"))
    config.reset()

    ctx = Context(
        config.get_settings(),
        Policy(
            capture_stdout=True,
            errors_as_dicts=True,
            allow_writes=True,
            allow_interactive=False,
        ),
    )
    tools = {
        op.name: bind(op, ctx)
        for op in iter_operations(surface="mcp", include_writes=True)
    }

    yield tools

    ctx.close()
    config.reset()


def test_status_connects(mcp_tools):
    result = mcp_tools["status"]()
    assert result["connected"] is True
    assert "password" not in result


def test_search_schema_and_read(mcp_tools):
    found = mcp_tools["search_entities"](ask_query="[[Category:Item]]", limit=5)
    assert "titles" in found

    category_schema = mcp_tools["get_category_schema"](category="Category:Item")
    assert "exists" in category_schema

    # An ask query has no defined result order and a category can hold pages
    # without a jsondata slot, so check every hit rather than trusting the first.
    titles = found["titles"]
    if titles:
        with_jsondata = []
        for title in titles:
            entity = mcp_tools["get_entity"](title=title)
            assert entity["title"] == title
            assert entity["exists"] is True

            page_slots = mcp_tools["list_page_slots"](title=title)
            assert page_slots["exists"] is True
            if any(s["key"] == "jsondata" for s in page_slots["slots"]):
                with_jsondata.append(title)
        assert with_jsondata, f"no jsondata slot on any of {titles}"


def test_delete_guard_blocks_untracked(mcp_tools):
    # A page the server never created must be refused without confirmation;
    # this returns before any network delete, so it never mutates the instance.
    result = mcp_tools["delete_entity"](title="Item:OSWdoesnotexistguardcheck")
    assert result["type"] == "ExternalDeleteBlocked"
