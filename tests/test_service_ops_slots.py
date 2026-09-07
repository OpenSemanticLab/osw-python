"""Unit tests for osw.service.ops.slots (Operation.fn called directly).

Importing ``osw.service.ops.slots`` registers its operations in
``osw.service.registry.REGISTRY`` at import time, so this module must not
clear the registry the way ``test_service_registry.py`` does.
"""

from unittest.mock import MagicMock

import pytest

from osw.service import errors, registry
from osw.service.config import Settings
from osw.service.context import Context, Policy
from osw.service.ledger import LedgerRecord
from osw.service.ops import slots


def _settings() -> Settings:
    return Settings(domain="wiki.example.org", username="u", password="p")


def _osw_with_page(exists=True, present_slots=()):
    page = MagicMock()
    page.exists = exists
    page._slots = list(present_slots)
    osw = MagicMock()
    osw.site.get_page.return_value.pages = [page]
    return osw, page


# -- list_page_slots --------------------------------------------------------
def test_list_page_slots_missing_page():
    osw, _ = _osw_with_page(exists=False)
    ctx = Context(_settings(), Policy(), osw=osw)

    result = slots.list_page_slots(ctx, title="Item:OSW1")

    assert result == {
        "title": "Item:OSW1",
        "exists": False,
        "slots": [],
        "valid_slot_keys": list(slots.SLOTS),
    }


def test_list_page_slots_existing_page():
    osw, page = _osw_with_page(present_slots=["main", "jsondata"])
    page.get_slot_content.side_effect = lambda key: "" if key == "main" else {"a": 1}
    page.get_slot_content_model.side_effect = lambda key: (
        "wikitext" if key == "main" else "json"
    )
    ctx = Context(_settings(), Policy(), osw=osw)

    result = slots.list_page_slots(ctx, title="Item:OSW1")

    assert result["title"] == "Item:OSW1"
    assert result["exists"] is True
    assert result["slots"] == [
        {"key": "main", "content_model": "wikitext", "empty": True},
        {"key": "jsondata", "content_model": "json", "empty": False},
    ]
    assert result["valid_slot_keys"] == list(slots.SLOTS)


# -- get_slot ----------------------------------------------------------------
def test_get_slot_rejects_unknown_slot():
    ctx = Context(_settings(), Policy(), osw=MagicMock())

    with pytest.raises(errors.InvalidSlot):
        slots.get_slot(ctx, title="Item:OSW1", slot="bogus")


def test_get_slot_missing_page_returns_not_exists():
    osw, _ = _osw_with_page(exists=False)
    ctx = Context(_settings(), Policy(), osw=osw)

    result = slots.get_slot(ctx, title="Item:OSW1", slot="jsondata")

    assert result == {
        "title": "Item:OSW1",
        "slot": "jsondata",
        "exists": False,
        "content": None,
    }


def test_get_slot_missing_slot_returns_not_exists():
    osw, _page = _osw_with_page(present_slots=["main"])
    ctx = Context(_settings(), Policy(), osw=osw)

    result = slots.get_slot(ctx, title="Item:OSW1", slot="jsondata")

    assert result == {
        "title": "Item:OSW1",
        "slot": "jsondata",
        "exists": False,
        "content": None,
    }


def test_get_slot_existing_slot():
    osw, page = _osw_with_page(present_slots=["jsondata"])
    page.get_slot_content.return_value = {"label": [{"text": "X"}]}
    page.get_slot_content_model.return_value = "json"
    ctx = Context(_settings(), Policy(), osw=osw)

    result = slots.get_slot(ctx, title="Item:OSW1", slot="jsondata")

    assert result["exists"] is True
    assert result["content_model"] == "json"
    assert result["content"] == {"label": [{"text": "X"}]}
    assert result["truncated"] is False
    page.get_slot_content.assert_called_with("jsondata")


# -- set_slot ------------------------------------------------------------
def test_set_slot_rejects_unknown_slot():
    ctx = Context(_settings(), Policy(), osw=MagicMock())

    with pytest.raises(errors.InvalidSlot):
        slots.set_slot(ctx, title="Item:OSW1", slot="bogus", content="x")


def test_set_slot_rejects_wrong_content_type_json():
    ctx = Context(_settings(), Policy(), osw=MagicMock())

    with pytest.raises(errors.InvalidContent):
        slots.set_slot(ctx, title="Item:OSW1", slot="jsondata", content="not-json")


def test_set_slot_rejects_wrong_content_type_wikitext():
    ctx = Context(_settings(), Policy(), osw=MagicMock())

    with pytest.raises(errors.InvalidContent):
        slots.set_slot(ctx, title="Item:OSW1", slot="main", content={"not": "a string"})


def test_set_slot_missing_slot_without_create_raises_slot_missing():
    osw, page = _osw_with_page(present_slots=[])
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.SlotMissing):
        slots.set_slot(
            ctx,
            title="Item:OSW1",
            slot="jsondata",
            content={"a": 1},
            create_if_missing=False,
        )
    page.create_slot.assert_not_called()
    page.set_slot_content.assert_not_called()


def test_set_slot_creates_missing_slot_when_allowed():
    osw, page = _osw_with_page(present_slots=[])
    page.get_url.return_value = "https://wiki.example.org/wiki/Item:OSW1"
    ctx = Context(_settings(), Policy(), osw=osw)

    result = slots.set_slot(ctx, title="Item:OSW1", slot="jsondata", content={"a": 1})

    page.create_slot.assert_called_once_with("jsondata", "json")
    page.set_slot_content.assert_called_once_with("jsondata", {"a": 1})
    page.edit.assert_called_once()
    assert result == {
        "title": "Item:OSW1",
        "slot": "jsondata",
        "changed": True,
        "url": "https://wiki.example.org/wiki/Item:OSW1",
    }


def test_set_slot_existing_slot_skips_create():
    osw, page = _osw_with_page(present_slots=["jsondata"])
    page.get_url.return_value = "https://wiki.example.org/wiki/Item:OSW1"
    ctx = Context(_settings(), Policy(), osw=osw)

    result = slots.set_slot(ctx, title="Item:OSW1", slot="jsondata", content={"a": 1})

    page.create_slot.assert_not_called()
    page.set_slot_content.assert_called_once_with("jsondata", {"a": 1})
    assert result["changed"] is True


# -- records= (ledger hook) -------------------------------------------------
def test_set_slot_records_matches_old_inline_ledger_call():
    op = registry.REGISTRY["set_slot"]

    result = {
        "title": "Item:OSW1",
        "slot": "jsondata",
        "changed": True,
        "url": "https://wiki.example.org/wiki/Item:OSW1",
    }

    assert op.records(result) == [
        LedgerRecord(title="Item:OSW1", op="update", slots=["jsondata"])
    ]


def test_set_slot_records_empty_when_not_changed():
    op = registry.REGISTRY["set_slot"]

    assert (
        op.records({"title": "Item:OSW1", "slot": "jsondata", "changed": False}) == []
    )


def test_set_slot_records_empty_when_changed_key_absent():
    op = registry.REGISTRY["set_slot"]

    assert op.records({"title": "Item:OSW1", "slot": "jsondata"}) == []


def test_set_slot_error_paths_do_not_reach_bind_records():
    """The invalid-input/slot-missing paths raise, so bind() never calls
    op.records for them -- matching the old code, which returned before
    reaching ``ledger.record``."""
    op = registry.REGISTRY["set_slot"]
    fake_ledger = MagicMock()
    ctx = Context(
        _settings(), Policy(errors_as_dicts=True), osw=MagicMock(), ledger=fake_ledger
    )
    bound = registry.bind(op, ctx)

    result = bound(title="Item:OSW1", slot="bogus", content="x")

    assert result["type"] == "InvalidSlot"
    fake_ledger.record.assert_not_called()
