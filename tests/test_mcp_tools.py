"""Unit tests for osw.mcp tool wiring and the delete provenance guard.

These mock the shared connection so no network is required.
"""

from unittest.mock import MagicMock

import pytest
import yaml

pytest.importorskip("mcp", reason="requires the osw[mcp] extra")
pytest.importorskip("dotenv", reason="requires the osw[mcp] extra")

from osw.mcp import connection
from osw.mcp.tools import entities, search, slots
from osw.service import config


class FakeMCP:
    """Minimal stand-in that captures @tool-decorated functions by name."""

    def __init__(self):
        self.tools = {}

    def tool(self, *_a, **_k):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn

        return deco


@pytest.fixture
def env(monkeypatch, tmp_path):
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("OSW_MCP_ENV_FILE", str(empty))
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "u")
    monkeypatch.setenv("OSW_PASSWORD", "p")
    monkeypatch.setenv("OSW_MCP_STATE_DIR", str(tmp_path / "state"))
    config.reset()
    connection._osw = None
    connection._ledger = None
    yield
    config.reset()
    connection._osw = None
    connection._ledger = None


def _osw_with_page(exists=True):
    page = MagicMock()
    page.exists = exists
    osw = MagicMock()
    osw.site.get_page.return_value.pages = [page]
    return osw, page


# -- delete guard ---------------------------------------------------------
def test_delete_untracked_is_blocked(env, monkeypatch):
    osw, page = _osw_with_page()
    monkeypatch.setattr(connection, "get_osw", lambda: osw)
    fake = FakeMCP()
    entities.register(fake, include_writes=True)

    result = fake.tools["delete_entity"](title="Item:OSWx")

    assert result["type"] == "ExternalDeleteBlocked"
    osw.site.get_page.assert_not_called()  # never even fetched the page
    page.delete.assert_not_called()


def test_delete_tracked_is_allowed(env, monkeypatch):
    osw, page = _osw_with_page()
    monkeypatch.setattr(connection, "get_osw", lambda: osw)
    connection.get_ledger().record("Item:OSWx", op="create", tool="t")
    fake = FakeMCP()
    entities.register(fake, include_writes=True)

    result = fake.tools["delete_entity"](title="Item:OSWx")

    assert result == {"title": "Item:OSWx", "deleted": True}
    page.delete.assert_called_once()
    # deletion untracks the entry
    assert connection.get_ledger().is_tracked("Item:OSWx") is False


def test_delete_external_with_confirm(env, monkeypatch):
    osw, page = _osw_with_page()
    monkeypatch.setattr(connection, "get_osw", lambda: osw)
    fake = FakeMCP()
    entities.register(fake, include_writes=True)

    result = fake.tools["delete_entity"](
        title="Item:OSWy", confirm_external_delete=True
    )

    assert result["deleted"] is True
    page.delete.assert_called_once()


def test_delete_nonexistent_page(env, monkeypatch):
    osw, page = _osw_with_page(exists=False)
    monkeypatch.setattr(connection, "get_osw", lambda: osw)
    connection.get_ledger().record("Item:OSWz", op="create", tool="t")
    fake = FakeMCP()
    entities.register(fake, include_writes=True)

    result = fake.tools["delete_entity"](title="Item:OSWz")

    assert result["deleted"] is False
    assert result["type"] == "NotFound"
    page.delete.assert_not_called()


# -- read wiring ----------------------------------------------------------
def test_get_entity_reads_jsondata_slot(env, monkeypatch):
    page = MagicMock()
    page.exists = True
    page.get_slot_content.return_value = {"label": [{"text": "X"}]}
    page.get_url.return_value = "https://wiki.example.org/wiki/Item:OSW1"
    osw = MagicMock()
    osw.site.get_page.return_value.pages = [page]
    monkeypatch.setattr(connection, "get_osw", lambda: osw)
    fake = FakeMCP()
    entities.register(fake, include_writes=False)

    result = fake.tools["get_entity"](title="Item:OSW1")

    assert result["exists"] is True
    assert result["jsondata"] == {"label": [{"text": "X"}]}
    page.get_slot_content.assert_called_with("jsondata")


def test_search_entities_calls_semantic_search(env, monkeypatch):
    osw = MagicMock()
    osw.site.semantic_search.return_value = ["Item:OSW1", "Item:OSW2"]
    monkeypatch.setattr(connection, "get_osw", lambda: osw)
    fake = FakeMCP()
    search.register(fake)

    result = fake.tools["search_entities"](ask_query="[[Category:Item]]")

    assert result["titles"] == ["Item:OSW1", "Item:OSW2"]
    assert result["count"] == 2
    osw.site.semantic_search.assert_called_once()


def test_read_only_registration_omits_writes(env):
    fake = FakeMCP()
    entities.register(fake, include_writes=False)
    assert "get_entity" in fake.tools
    assert "create_or_update_entity" not in fake.tools
    assert "delete_entity" not in fake.tools


# -- set_slot validation (no network) -------------------------------------
def test_set_slot_rejects_unknown_slot(env, monkeypatch):
    monkeypatch.setattr(connection, "get_osw", lambda: MagicMock())
    fake = FakeMCP()
    slots.register(fake, include_writes=True)

    result = fake.tools["set_slot"](title="Item:OSW1", slot="bogus", content="x")

    assert result["type"] == "InvalidSlot"


def test_set_slot_rejects_wrong_content_type(env, monkeypatch):
    monkeypatch.setattr(connection, "get_osw", lambda: MagicMock())
    fake = FakeMCP()
    slots.register(fake, include_writes=True)

    result = fake.tools["set_slot"](
        title="Item:OSW1", slot="jsondata", content="not-json"
    )

    assert result["type"] == "InvalidContent"


def test_sparql_without_endpoint_reports_not_configured(env, monkeypatch):
    monkeypatch.setattr(connection, "get_osw", lambda: MagicMock())
    fake = FakeMCP()
    search.register(fake)

    result = fake.tools["sparql_query"](query="SELECT * WHERE {?s ?p ?o}")

    assert result["type"] == "NotConfigured"


def test_create_or_update_entity_uses_active_domain(env, monkeypatch, tmp_path):
    """The response urls use the active domain, not a stale/static one."""
    cred_file = tmp_path / "accounts.yaml"
    cred_file.write_text(
        yaml.safe_dump({
            "wiki-a.example.org": {"username": "a", "password": "b"},
            "wiki-b.example.org": {"username": "c", "password": "d"},
        }),
        encoding="utf-8",
    )
    monkeypatch.delenv("OSW_DOMAIN", raising=False)
    monkeypatch.delenv("OSW_USERNAME", raising=False)
    monkeypatch.delenv("OSW_PASSWORD", raising=False)
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))
    config.reset()
    connection._osw = None
    connection._ledger = None
    config.set_active_instance("wiki-b.example.org")

    osw = MagicMock()
    osw.fetch_schema.return_value = MagicMock(error_messages=[])
    osw.store_entity.return_value = MagicMock(
        pages={"Item:OSW1": MagicMock()}, change_id="c1"
    )
    monkeypatch.setattr(connection, "get_osw", lambda: osw)
    monkeypatch.setattr(
        entities,
        "_resolve_category_class",
        lambda category: entities.model_entity.Entity,
    )
    fake = FakeMCP()
    entities.register(fake, include_writes=True)

    result = fake.tools["create_or_update_entity"](
        category="Category:Item", jsondata={"label": [{"text": "Test"}]}
    )

    assert result["urls"] == ["https://wiki-b.example.org/wiki/Item:OSW1"]


def test_run_guarded_converts_exceptions(env, monkeypatch):
    osw = MagicMock()
    osw.site.get_page.side_effect = RuntimeError("boom")
    monkeypatch.setattr(connection, "get_osw", lambda: osw)
    fake = FakeMCP()
    entities.register(fake, include_writes=False)

    result = fake.tools["get_entity"](title="Item:OSW1")

    assert result["type"] == "RuntimeError"
    assert "boom" in result["error"]
