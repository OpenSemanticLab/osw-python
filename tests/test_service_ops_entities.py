"""Unit tests for osw.service.ops.entities (Operation.fn called directly).

Importing ``osw.service.ops.entities`` registers its operations in
``osw.service.registry.REGISTRY`` at import time, so this module must not
clear the registry the way ``test_service_registry.py`` does.
"""

from unittest.mock import MagicMock

import pytest

from osw.service import errors, registry
from osw.service.config import Settings
from osw.service.context import Context, Policy
from osw.service.ledger import LedgerRecord
from osw.service.ops import entities


def _settings() -> Settings:
    return Settings(domain="wiki.example.org", username="u", password="p")


def _osw_with_page(exists=True):
    page = MagicMock()
    page.exists = exists
    osw = MagicMock()
    osw.site.get_page.return_value.pages = [page]
    return osw, page


# -- get_entity --------------------------------------------------------------
def test_get_entity_missing_page_returns_not_exists():
    osw, _ = _osw_with_page(exists=False)
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.get_entity(ctx, title="Item:OSW1")

    assert result == {"title": "Item:OSW1", "exists": False, "jsondata": None}


def test_get_entity_reads_jsondata_slot():
    osw, page = _osw_with_page()
    page.get_slot_content.return_value = {"label": [{"text": "X"}]}
    page.get_url.return_value = "https://wiki.example.org/wiki/Item:OSW1"
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.get_entity(ctx, title="Item:OSW1")

    assert result["exists"] is True
    assert result["jsondata"] == {"label": [{"text": "X"}]}
    page.get_slot_content.assert_called_with("jsondata")


# -- export_entity_jsonld -----------------------------------------------------
def test_export_entity_jsonld_returns_jsonld():
    osw = MagicMock()
    osw.load_entity.return_value = MagicMock(entities=[MagicMock()])
    osw.export_jsonld.return_value = MagicMock(
        documents=[{"@id": "Item:OSW1"}], graph=None
    )
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.export_entity_jsonld(ctx, title="Item:OSW1")

    assert result == {"jsonld": {"@id": "Item:OSW1"}}


def test_export_entity_jsonld_not_found_raises():
    osw = MagicMock()
    osw.load_entity.return_value = MagicMock(entities=[])
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.NotFound):
        entities.export_entity_jsonld(ctx, title="Item:OSW404")


# -- create_or_update_entity ---------------------------------------------------
def test_create_or_update_entity_uses_active_domain(monkeypatch):
    osw = MagicMock()
    osw.fetch_schema.return_value = MagicMock(error_messages=[])
    osw.store_entity.return_value = MagicMock(
        pages={"Item:OSW1": MagicMock()}, change_id="c1"
    )
    monkeypatch.setattr(
        entities, "_resolve_category_class", lambda category: entities.model_entity.Item
    )
    monkeypatch.setattr(
        entities.config, "get_active_domain", lambda: "wiki-b.example.org"
    )
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.create_or_update_entity(
        ctx, category="Category:Item", jsondata={"label": [{"text": "Test"}]}
    )

    assert result["titles"] == ["Item:OSW1"]
    assert result["change_id"] == "c1"
    assert result["urls"] == ["https://wiki-b.example.org/wiki/Item:OSW1"]


def test_create_or_update_entity_schema_error_raises():
    osw = MagicMock()
    osw.fetch_schema.return_value = MagicMock(error_messages=["bad schema"])
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.SchemaError):
        entities.create_or_update_entity(ctx, category="Category:Item", jsondata={})


def test_create_or_update_entity_class_not_found_raises(monkeypatch):
    osw = MagicMock()
    osw.fetch_schema.return_value = MagicMock(error_messages=[])
    monkeypatch.setattr(entities, "_resolve_category_class", lambda category: None)
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.ClassNotFound):
        entities.create_or_update_entity(ctx, category="Category:Bogus", jsondata={})


def test_create_or_update_entity_validation_error_raises(monkeypatch):
    osw = MagicMock()
    osw.fetch_schema.return_value = MagicMock(error_messages=[])

    class _Boom:
        def __init__(self, **kwargs):
            raise ValueError("nope")

    monkeypatch.setattr(entities, "_resolve_category_class", lambda category: _Boom)
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.ValidationError):
        entities.create_or_update_entity(ctx, category="Category:Item", jsondata={})


# -- records= (ledger hook) ----------------------------------------------------
def test_create_or_update_entity_records_matches_old_inline_ledger_call():
    op = registry.REGISTRY["create_or_update_entity"]

    result = {
        "titles": ["Item:OSW1", "Item:OSW2"],
        "change_id": "c1",
        "urls": [
            "https://wiki.example.org/wiki/Item:OSW1",
            "https://wiki.example.org/wiki/Item:OSW2",
        ],
    }

    assert op.records(result) == [
        LedgerRecord(
            title="Item:OSW1", op="create_or_update", change_id="c1", slots=["jsondata"]
        ),
        LedgerRecord(
            title="Item:OSW2", op="create_or_update", change_id="c1", slots=["jsondata"]
        ),
    ]


def test_create_or_update_entity_records_empty_when_no_titles():
    op = registry.REGISTRY["create_or_update_entity"]

    assert op.records({"titles": [], "change_id": "c1", "urls": []}) == []


def test_create_or_update_entity_schema_error_does_not_reach_bind_records():
    op = registry.REGISTRY["create_or_update_entity"]
    osw = MagicMock()
    osw.fetch_schema.return_value = MagicMock(error_messages=["boom"])
    fake_ledger = MagicMock()
    ctx = Context(
        _settings(), Policy(errors_as_dicts=True), osw=osw, ledger=fake_ledger
    )
    bound = registry.bind(op, ctx)

    result = bound(category="Category:Item", jsondata={"label": [{"text": "Test"}]})

    assert result["type"] == "SchemaError"
    fake_ledger.record.assert_not_called()


# -- delete_entity --------------------------------------------------------
def test_delete_untracked_is_blocked():
    osw, page = _osw_with_page()
    ledger = MagicMock()
    ledger.is_tracked.return_value = False
    ctx = Context(_settings(), Policy(), osw=osw, ledger=ledger)

    with pytest.raises(errors.ExternalDeleteBlocked) as exc_info:
        entities.delete_entity(ctx, title="Item:OSWx")

    assert exc_info.value.payload()["title"] == "Item:OSWx"
    osw.site.get_page.assert_not_called()  # never even fetched the page
    page.delete.assert_not_called()


def test_delete_tracked_is_allowed():
    osw, page = _osw_with_page()
    ledger = MagicMock()
    ledger.is_tracked.return_value = True
    ctx = Context(_settings(), Policy(), osw=osw, ledger=ledger)

    result = entities.delete_entity(ctx, title="Item:OSWx")

    assert result == {"title": "Item:OSWx", "deleted": True}
    page.delete.assert_called_once()
    ledger.mark_deleted.assert_called_once_with("Item:OSWx")


def test_delete_external_with_confirm():
    osw, page = _osw_with_page()
    ledger = MagicMock()
    ledger.is_tracked.return_value = False
    ctx = Context(_settings(), Policy(), osw=osw, ledger=ledger)

    result = entities.delete_entity(
        ctx, title="Item:OSWy", confirm_external_delete=True
    )

    assert result == {"title": "Item:OSWy", "deleted": True}
    page.delete.assert_called_once()


def test_delete_nonexistent_page_raises():
    osw, page = _osw_with_page(exists=False)
    ledger = MagicMock()
    ledger.is_tracked.return_value = True
    ctx = Context(_settings(), Policy(), osw=osw, ledger=ledger)

    with pytest.raises(errors.NotFound) as exc_info:
        entities.delete_entity(ctx, title="Item:OSWz")

    assert exc_info.value.payload() == {
        "title": "Item:OSWz",
        "deleted": False,
        "error": "Page 'Item:OSWz' does not exist.",
        "type": "NotFound",
    }
    page.delete.assert_not_called()
