"""Unit tests for osw.service.ops.tasks (Operation.fn called directly).

Importing ``osw.service.ops.tasks`` registers its operations in
``osw.service.registry.REGISTRY`` at import time, so this module must not
clear the registry the way ``test_service_registry.py`` does.
"""

from typing import Any, Optional
from unittest.mock import MagicMock

import pytest
from opensemantic.base.v1 import OswBaseModel

from osw.service import errors
from osw.service.config import Settings
from osw.service.context import Context, Policy
from osw.service.ops import tasks


def _settings(**overrides) -> Settings:
    return Settings(domain="wiki.example.org", username="u", password="p", **overrides)


def _smw_prop_map() -> dict:
    """The identity SMW property map used by tests that do not target
    ``_smw_props`` itself, matching the constants the existing fixtures
    already assert against."""
    return {
        "status": tasks.PROP_STATUS,
        "prio": tasks.PROP_PRIO,
        "related_to": tasks.PROP_RELATED_TO,
        "actionees": tasks.PROP_ACTIONEE,
        "label": tasks.PROP_LABEL,
    }


def _osw_with_page(jsondata, exists=True):
    page = MagicMock()
    page.exists = exists
    page.get_slot_content.return_value = jsondata
    osw = MagicMock()
    osw.site.get_page.return_value.pages = [page]
    osw.site.get_smw_property_map.return_value = _smw_prop_map()
    return osw, page


class _FakeEntityModel(OswBaseModel):
    """Stand-in for a generated Task/Person model, permissive enough to hold
    every field these tests write, so assertions can read them back."""

    uuid: Optional[Any] = None
    type: Optional[Any] = None
    label: Optional[Any] = None
    description: Optional[Any] = None
    status: Optional[Any] = None
    prio: Optional[Any] = None
    related_to: Optional[Any] = None
    actionees: Optional[Any] = None
    end_date_time: Optional[Any] = None
    first_name: Optional[Any] = None
    surname: Optional[Any] = None
    email: Optional[Any] = None

    class Config:
        extra = "allow"


def _ask_row(fulltext, fullurl, displaytitle, printouts=None):
    return {
        "fulltext": fulltext,
        "fullurl": fullurl,
        "displaytitle": displaytitle,
        "exists": "1",
        "printouts": printouts or {},
    }


def _ask_response(rows_by_title):
    return [{"query": {"results": rows_by_title}}]


# -- create_task ---------------------------------------------------------
def test_create_task_minimal_defaults_status_to_do(monkeypatch):
    osw = MagicMock()
    osw.store_entity.return_value = MagicMock(
        pages={"Item:OSW1": MagicMock()}, change_id="c1"
    )
    monkeypatch.setattr(
        tasks, "_resolve_category_class", lambda category: _FakeEntityModel
    )
    monkeypatch.setattr(tasks.config, "get_settings", lambda: _settings())
    monkeypatch.setattr(tasks.config, "get_active_domain", lambda: "wiki.example.org")
    ctx = Context(_settings(), Policy(), osw=osw)

    result = tasks.create_task(ctx, label="Do the thing")

    assert result["title"] == "Item:OSW1"
    assert result["change_id"] == "c1"
    osw.store_entity.assert_called_once()
    entity = osw.store_entity.call_args[0][0].entities[0]
    assert entity.type == [tasks.CATEGORY_TASK]
    assert entity.uuid == result["uuid"]
    assert entity.label == [{"text": "Do the thing", "lang": "en"}]
    assert entity.status == tasks.STATUS_ITEMS["to do"]


def test_create_task_status_alias_maps_to_in_work(monkeypatch):
    osw = MagicMock()
    osw.store_entity.return_value = MagicMock(
        pages={"Item:OSW2": MagicMock()}, change_id="c2"
    )
    monkeypatch.setattr(
        tasks, "_resolve_category_class", lambda category: _FakeEntityModel
    )
    monkeypatch.setattr(tasks.config, "get_settings", lambda: _settings())
    monkeypatch.setattr(tasks.config, "get_active_domain", lambda: "wiki.example.org")
    ctx = Context(_settings(), Policy(), osw=osw)

    tasks.create_task(ctx, label="X", status="in progress")

    entity = osw.store_entity.call_args[0][0].entities[0]
    assert entity.status == tasks.STATUS_ITEMS["in work"]


def test_create_task_unknown_status_raises(monkeypatch):
    monkeypatch.setattr(tasks.config, "get_settings", lambda: _settings())
    ctx = Context(_settings(), Policy(), osw=MagicMock())

    with pytest.raises(errors.ValidationError) as exc_info:
        tasks.create_task(ctx, label="X", status="bogus")

    message = str(exc_info.value)
    assert "to do" in message
    assert "in work" in message
    assert "done" in message


def test_create_task_writes_project_into_related_to(monkeypatch):
    osw = MagicMock()
    osw.site.get_smw_property_map.return_value = _smw_prop_map()
    osw.site.semantic_search.return_value = _ask_response({
        "Item:OSWproj1": _ask_row(
            "Item:OSWproj1",
            "https://wiki.example.org/wiki/Item:OSWproj1",
            "My Project",
        )
    })
    osw.store_entity.return_value = MagicMock(
        pages={"Item:OSW3": MagicMock()}, change_id="c3"
    )
    monkeypatch.setattr(
        tasks, "_resolve_category_class", lambda category: _FakeEntityModel
    )
    monkeypatch.setattr(tasks.config, "get_settings", lambda: _settings())
    monkeypatch.setattr(tasks.config, "get_active_domain", lambda: "wiki.example.org")
    ctx = Context(_settings(), Policy(), osw=osw)

    tasks.create_task(ctx, label="X", project="My Project")

    entity = osw.store_entity.call_args[0][0].entities[0]
    assert entity.related_to == ["Item:OSWproj1"]
    assert not hasattr(entity, "belongs_to_project")


# -- create_person -----------------------------------------
def test_create_person_uses_configured_category(monkeypatch):
    settings = _settings(person_category="Category:OSWoverride")
    osw = MagicMock()
    osw.site.get_smw_property_map.return_value = _smw_prop_map()
    osw.store_entity.return_value = MagicMock(
        pages={"Item:OSWp1": MagicMock()}, change_id="c4"
    )
    monkeypatch.setattr(
        tasks, "_resolve_category_class", lambda category: _FakeEntityModel
    )
    monkeypatch.setattr(tasks.config, "get_settings", lambda: settings)
    monkeypatch.setattr(tasks.config, "get_active_domain", lambda: "wiki.example.org")
    ctx = Context(settings, Policy(), osw=osw)

    tasks.create_person(ctx, first_name="Ada", surname="Lovelace")

    entity = osw.store_entity.call_args[0][0].entities[0]
    assert entity.type == ["Category:OSWoverride"]


# -- _resolve_ref ----------------------------------------------------------
def test_resolve_ref_multiple_matches_raises():
    osw = MagicMock()
    osw.site.get_smw_property_map.return_value = _smw_prop_map()
    osw.site.semantic_search.return_value = _ask_response({
        "Item:OSWa": _ask_row(
            "Item:OSWa", "https://wiki.example.org/wiki/Item:OSWa", "Alpha"
        ),
        "Item:OSWb": _ask_row(
            "Item:OSWb", "https://wiki.example.org/wiki/Item:OSWb", "Beta"
        ),
    })
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.ValidationError) as exc_info:
        tasks._resolve_ref(ctx, "a", tasks.CATEGORY_PROJECT, "project")

    message = str(exc_info.value)
    assert "Alpha (Item:OSWa)" in message
    assert "Beta (Item:OSWb)" in message


def test_resolve_ref_no_matches_raises_not_found():
    osw = MagicMock()
    osw.site.get_smw_property_map.return_value = _smw_prop_map()
    osw.site.semantic_search.return_value = [{"query": {"results": []}}]
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.NotFound):
        tasks._resolve_ref(ctx, "nope", tasks.CATEGORY_PERSON, "person")


def test_resolve_ref_rejects_injection_value():
    osw = MagicMock()
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.ValidationError):
        tasks._resolve_ref(ctx, "x]]y", tasks.CATEGORY_PROJECT, "project")

    osw.site.semantic_search.assert_not_called()


def test_resolve_ref_queries_the_renamed_label_property_not_the_fallback():
    """Rename the label property to prove the lookup query follows the
    ``@context`` of the category rather than ``tasks.PROP_LABEL``."""
    osw = MagicMock()
    osw.site.get_smw_property_map.return_value = {"label": "WikiLabel"}
    osw.site.semantic_search.return_value = _ask_response({
        "Item:OSWa": _ask_row(
            "Item:OSWa", "https://wiki.example.org/wiki/Item:OSWa", "Alpha"
        )
    })
    ctx = Context(_settings(), Policy(), osw=osw)

    tasks._resolve_ref(ctx, "a", tasks.CATEGORY_PROJECT, "project")

    query = osw.site.semantic_search.call_args[0][0].query[0]
    assert "WikiLabel" in query
    assert tasks.PROP_LABEL not in query


# -- update_task -------------------------------------------------------------
def test_update_task_preserves_unnamed_field_and_reports_changed(monkeypatch):
    stored = {
        "uuid": "u1",
        "type": ["Category:OSWtaskcore"],
        "label": [{"text": "Old", "lang": "en"}],
        "foo": "bar",
    }
    osw, _ = _osw_with_page(stored)
    osw.store_entity.return_value = MagicMock(
        pages={"Item:OSWtask1": MagicMock()}, change_id="c5"
    )
    monkeypatch.setattr(
        tasks, "_resolve_category_class", lambda category: _FakeEntityModel
    )
    monkeypatch.setattr(tasks.config, "get_settings", lambda: _settings())
    monkeypatch.setattr(tasks.config, "get_active_domain", lambda: "wiki.example.org")
    ctx = Context(_settings(), Policy(), osw=osw)

    result = tasks.update_task(ctx, title="Item:OSWtask1", label="New")

    assert result["changed"] == ["label"]
    entity = osw.store_entity.call_args[0][0].entities[0]
    assert entity.foo == "bar"
    assert entity.uuid == "u1"
    assert entity.label == [{"text": "New", "lang": "en"}]


def test_update_task_missing_page_raises_not_found():
    osw, _ = _osw_with_page({}, exists=False)
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.NotFound):
        tasks.update_task(ctx, title="Item:OSWmissing", label="New")


# -- _ensure_models ------------------------------------------------------------
def test_ensure_models_fetches_only_when_missing(monkeypatch):
    osw = MagicMock()
    osw.fetch_schema.return_value = MagicMock(error_messages=[])
    monkeypatch.setattr(tasks.config, "get_settings", lambda: _settings())
    ctx = Context(_settings(), Policy(), osw=osw)

    monkeypatch.setattr(tasks, "_resolve_category_class", lambda category: None)
    tasks._ensure_models(ctx)
    assert osw.fetch_schema.call_count == 1

    osw.fetch_schema.reset_mock()
    monkeypatch.setattr(
        tasks, "_resolve_category_class", lambda category: _FakeEntityModel
    )
    tasks._ensure_models(ctx)
    assert osw.fetch_schema.call_count == 0


def test_ensure_models_restores_a_disabled_page_cache(monkeypatch):
    """fetch_schema turns the page cache on and leaves it on.

    A cache left on makes a later read return a revision from before a write
    in the same process, so _ensure_models has to restore the prior state.
    """
    osw = MagicMock()
    osw.fetch_schema.return_value = MagicMock(error_messages=[])
    osw.site.get_cache_enabled.return_value = False
    monkeypatch.setattr(tasks.config, "get_settings", lambda: _settings())
    monkeypatch.setattr(tasks, "_resolve_category_class", lambda category: None)
    ctx = Context(_settings(), Policy(), osw=osw)

    tasks._ensure_models(ctx)

    osw.site.disable_cache.assert_called_once()
    osw.site.enable_cache.assert_not_called()


# -- _store --------------------------------------------------------------------
def test_store_raises_when_the_written_page_does_not_exist(monkeypatch):
    """store_entity reports a title even when it skipped the upload."""
    osw, _ = _osw_with_page({}, exists=False)
    osw.store_entity.return_value = MagicMock(
        pages={"Item:OSWghost": MagicMock()}, change_id="c6"
    )
    monkeypatch.setattr(
        tasks, "_resolve_category_class", lambda category: _FakeEntityModel
    )
    monkeypatch.setattr(tasks.config, "get_settings", lambda: _settings())
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.OpError) as exc_info:
        tasks.create_task(ctx, label="X")

    assert "Item:OSWghost" in str(exc_info.value)


def test_create_person_sends_a_label_built_from_the_two_name_fields(monkeypatch):
    """The schema's label template only runs in the browser form."""
    osw = MagicMock()
    osw.site.get_page.return_value.pages = [MagicMock(exists=True)]
    osw.store_entity.return_value = MagicMock(
        pages={"Item:OSWp2": MagicMock()}, change_id="c7"
    )
    monkeypatch.setattr(
        tasks, "_resolve_category_class", lambda category: _FakeEntityModel
    )
    monkeypatch.setattr(tasks.config, "get_settings", lambda: _settings())
    monkeypatch.setattr(tasks.config, "get_active_domain", lambda: "wiki.example.org")
    ctx = Context(_settings(), Policy(), osw=osw)

    tasks.create_person(ctx, first_name="Ada", surname="Lovelace")

    entity = osw.store_entity.call_args[0][0].entities[0]
    assert entity.label == [{"text": "Ada Lovelace", "lang": "en"}]
    assert entity.first_name == "Ada"
    assert entity.surname == "Lovelace"


def test_update_task_reads_the_page_with_the_cache_disabled(monkeypatch):
    """A cached page object can hold a revision from before an earlier write."""
    osw, _ = _osw_with_page({"uuid": "u2", "type": ["Category:OSWtaskcore"]})
    osw.site.get_cache_enabled.return_value = True
    osw.store_entity.return_value = MagicMock(
        pages={"Item:OSWtask2": MagicMock()}, change_id="c8"
    )
    monkeypatch.setattr(
        tasks, "_resolve_category_class", lambda category: _FakeEntityModel
    )
    monkeypatch.setattr(tasks.config, "get_settings", lambda: _settings())
    monkeypatch.setattr(tasks.config, "get_active_domain", lambda: "wiki.example.org")
    ctx = Context(_settings(), Policy(), osw=osw)

    tasks.update_task(ctx, title="Item:OSWtask2", status="done")

    osw.site.disable_cache.assert_called()
    # The caller had the cache on, so it has to be on again afterwards.
    assert osw.site.enable_cache.call_count == osw.site.disable_cache.call_count


def test_resolve_due_normalizes_a_date_and_rejects_an_impossible_one():
    """The regex only checks the shape, so the calendar date is parsed too."""
    assert tasks._resolve_due("2026-12-31") == "2026-12-31T00:00:00Z"
    assert tasks._resolve_due("  2026-12-31  ") == "2026-12-31T00:00:00Z"
    assert tasks._resolve_due("2026-12-31T08:30:00Z") == "2026-12-31T08:30:00Z"

    for bad in ("2026-13-45", "31.12.2026", "next friday", ""):
        with pytest.raises(errors.ValidationError):
            tasks._resolve_due(bad)


def test_create_task_returns_the_page_names_its_labels_resolved_to(monkeypatch):
    """A label search matches a substring, so the caller must see the choice."""
    osw = MagicMock()
    osw.site.get_smw_property_map.return_value = _smw_prop_map()
    osw.site.semantic_search.side_effect = [
        _ask_response({"Item:OSWproj9": _ask_row("Item:OSWproj9", "u", "ArkEve")}),
        _ask_response({"Item:OSWper9": _ask_row("Item:OSWper9", "u", "Ada Lovelace")}),
    ]
    osw.store_entity.return_value = MagicMock(
        pages={"Item:OSWnew": MagicMock()}, change_id="c9"
    )
    monkeypatch.setattr(
        tasks, "_resolve_category_class", lambda category: _FakeEntityModel
    )
    monkeypatch.setattr(tasks.config, "get_settings", lambda: _settings())
    monkeypatch.setattr(tasks.config, "get_active_domain", lambda: "wiki.example.org")
    ctx = Context(_settings(), Policy(), osw=osw)

    result = tasks.create_task(ctx, label="Fix it", project="ArkEve", actionees=["Ada"])

    assert result["related_to"] == ["Item:OSWproj9"]
    assert result["actionees"] == ["Item:OSWper9"]


def test_create_task_reference_list_survives_being_cleared_by_the_model(monkeypatch):
    """oold's LinkedBaseModel empties these lists in the dict it is given.

    The real model is not used here, so the clearing is simulated around
    ``_store``; the point is that the returned value is a copy taken before.
    """
    real_store = tasks._store

    def clearing_store(ctx_, category, jsondata, comment):
        result = real_store(ctx_, category, jsondata, comment)
        for key in ("related_to", "actionees"):
            if key in jsondata:
                jsondata[key].clear()
        return result

    osw = MagicMock()
    osw.site.get_smw_property_map.return_value = _smw_prop_map()
    osw.site.semantic_search.return_value = _ask_response({
        "Item:OSWper9": _ask_row("Item:OSWper9", "u", "Ada Lovelace")
    })
    osw.store_entity.return_value = MagicMock(
        pages={"Item:OSWnew2": MagicMock()}, change_id="c10"
    )
    monkeypatch.setattr(
        tasks, "_resolve_category_class", lambda category: _FakeEntityModel
    )
    monkeypatch.setattr(tasks.config, "get_settings", lambda: _settings())
    monkeypatch.setattr(tasks.config, "get_active_domain", lambda: "wiki.example.org")
    monkeypatch.setattr(tasks, "_store", clearing_store)
    ctx = Context(_settings(), Policy(), osw=osw)

    result = tasks.create_task(ctx, label="Fix it", actionees=["Ada"])

    assert result["actionees"] == ["Item:OSWper9"]


# -- _smw_props --------------------------------------------------------------
def test_smw_props_uses_values_from_get_smw_property_map():
    osw = MagicMock()
    osw.site.get_smw_property_map.return_value = {
        "status": "HasStatus",
        "label": "HasLabel",
    }
    ctx = Context(_settings(), Policy(), osw=osw)

    result = tasks._smw_props(ctx, tasks.CATEGORY_TASK, ["status", "label"])

    assert result == {"status": "HasStatus", "label": "HasLabel"}
    osw.site.get_smw_property_map.assert_called_once_with(tasks.CATEGORY_TASK)


def test_smw_props_missing_field_raises_op_error():
    osw = MagicMock()
    osw.site.get_smw_property_map.return_value = {"status": "HasStatus"}
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.OpError) as exc_info:
        tasks._smw_props(ctx, tasks.CATEGORY_TASK, ["status", "label"])

    message = str(exc_info.value)
    assert "label" in message
    assert tasks.CATEGORY_TASK in message


def test_smw_props_falls_back_and_warns_when_get_smw_property_map_fails():
    osw = MagicMock()
    osw.site.get_smw_property_map.side_effect = RuntimeError("boom")
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.warns(UserWarning, match=tasks.CATEGORY_TASK):
        result = tasks._smw_props(ctx, tasks.CATEGORY_TASK, ["status", "label"])

    assert result == {"status": tasks.PROP_STATUS, "label": tasks.PROP_LABEL}


def test_smw_props_falls_back_and_warns_when_get_smw_property_map_is_empty():
    """An empty mapping means the category page is probably missing or
    unreadable, not that the data model dropped every field, so this must
    fall back rather than raise ``errors.OpError``."""
    osw = MagicMock()
    osw.site.get_smw_property_map.return_value = {}
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.warns(UserWarning, match=tasks.CATEGORY_TASK):
        result = tasks._smw_props(ctx, tasks.CATEGORY_TASK, ["status", "label"])

    assert result == {"status": tasks.PROP_STATUS, "label": tasks.PROP_LABEL}


def test_smw_props_raises_op_error_for_a_field_without_a_fallback():
    """A field outside ``_PROP_FALLBACK`` must not be silently guessed; that
    would build a query that returns nothing and reports no error."""
    osw = MagicMock()
    osw.site.get_smw_property_map.side_effect = RuntimeError("boom")
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.OpError) as exc_info:
        tasks._smw_props(ctx, tasks.CATEGORY_TASK, ["status", "not_a_real_field"])

    assert "not_a_real_field" in str(exc_info.value)
