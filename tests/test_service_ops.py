"""Unit tests preserving the MCP-wrapper-level assertions from the old
``osw.mcp.tools`` test suite (``test_mcp_tools.py``, now removed).

Every operation body assertion from that file already lives in
``tests/test_service_ops_<group>.py`` (called directly, the way this module's
sibling ``test_service_ops_files.py`` does), and the generic ``bind()`` /
error-payload mechanics live in ``tests/test_service_registry.py`` and
``tests/test_service_errors.py``. What is kept here is the handful of
assertions that only made sense through the ``bind()`` wrapper -- e.g. an
``OpError`` becoming a structured dict rather than raising -- exercised
against the real, registered operations (not a synthetic ``fn``), so nothing
here duplicates that coverage.
"""

from unittest.mock import MagicMock

import osw.service.ops  # noqa: F401  (registers the operations)
from osw.service import registry
from osw.service.config import Settings
from osw.service.context import Context, Policy


def _settings() -> Settings:
    return Settings(domain="wiki.example.org", username="u", password="p")


def _osw_with_page(exists=True):
    page = MagicMock()
    page.exists = exists
    osw = MagicMock()
    osw.site.get_page.return_value.pages = [page]
    return osw, page


def _bound(name: str, ctx: Context):
    return registry.bind(registry.REGISTRY[name], ctx)


# -- delete_entity: bind() turns its guard/hybrid errors into dicts ---------
def test_delete_untracked_is_blocked_as_dict():
    osw, page = _osw_with_page()
    ledger = MagicMock()
    ledger.is_tracked.return_value = False
    ctx = Context(_settings(), Policy(errors_as_dicts=True), osw=osw, ledger=ledger)

    result = _bound("delete_entity", ctx)(title="Item:OSWx")

    assert result["type"] == "ExternalDeleteBlocked"
    osw.site.get_page.assert_not_called()  # never even fetched the page
    page.delete.assert_not_called()


def test_delete_nonexistent_page_returns_hybrid_dict():
    """delete_entity's NotFound carries {"title", "deleted": False} extras;
    bind() must merge them with {"error", "type"} rather than dropping either
    half of the shape."""
    osw, page = _osw_with_page(exists=False)
    ledger = MagicMock()
    ledger.is_tracked.return_value = True
    ctx = Context(_settings(), Policy(errors_as_dicts=True), osw=osw, ledger=ledger)

    result = _bound("delete_entity", ctx)(title="Item:OSWz")

    assert result == {
        "title": "Item:OSWz",
        "deleted": False,
        "error": "Page 'Item:OSWz' does not exist.",
        "type": "NotFound",
    }
    page.delete.assert_not_called()


def test_delete_tracked_is_allowed_as_dict():
    osw, page = _osw_with_page()
    ledger = MagicMock()
    ledger.is_tracked.return_value = True
    ctx = Context(_settings(), Policy(errors_as_dicts=True), osw=osw, ledger=ledger)

    result = _bound("delete_entity", ctx)(title="Item:OSWx")

    assert result == {"title": "Item:OSWx", "deleted": True}
    page.delete.assert_called_once()


# -- real registry write flags, no mcp SDK required --------------------------
def test_read_only_mcp_surface_omits_entity_writes():
    """A read-only server must not register create_or_update_entity/delete_entity,
    but must still register the reader; checked against the real registry
    (not a synthetic op) so a mis-flagged ``writes=`` on a real operation
    would be caught here too."""
    names = {
        op.name for op in registry.iter_operations(surface="mcp", include_writes=False)
    }
    assert "get_entity" in names
    assert "create_or_update_entity" not in names
    assert "delete_entity" not in names
