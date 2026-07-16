"""Integration tests for the osw-mcp server against a live OSL instance.

Excluded from the default run (tests/integration is ignored). Provide live
credentials to run:

    uv run pytest tests/integration/test_mcp_server.py -o addopts="" \
        --wiki_domain <domain> --wiki_username <user> --wiki_password <pass>

The wiki_* fixtures self-skip when credentials are absent.
"""

import pytest

from osw.mcp import config, connection
from osw.mcp.tools import entities, schema, search, slots, status


class _Collector:
    """Captures @tool-decorated functions so they can be called directly."""

    def __init__(self):
        self.tools = {}

    def tool(self, *_a, **_k):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn

        return deco


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
    connection._osw = None
    connection._ledger = None

    collector = _Collector()
    status.register(collector)
    search.register(collector)
    schema.register(collector)
    slots.register(collector, include_writes=True)
    entities.register(collector, include_writes=True)

    yield collector.tools

    connection.shutdown()
    connection._osw = None
    connection._ledger = None
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

    if found["titles"]:
        title = found["titles"][0]
        entity = mcp_tools["get_entity"](title=title)
        assert entity["title"] == title
        assert entity["exists"] is True

        page_slots = mcp_tools["list_page_slots"](title=title)
        assert page_slots["exists"] is True
        assert any(s["key"] == "jsondata" for s in page_slots["slots"])


def test_delete_guard_blocks_untracked(mcp_tools):
    # A page the server never created must be refused without confirmation;
    # this returns before any network delete, so it never mutates the instance.
    result = mcp_tools["delete_entity"](title="Item:OSWdoesnotexistguardcheck")
    assert result["type"] == "ExternalDeleteBlocked"
