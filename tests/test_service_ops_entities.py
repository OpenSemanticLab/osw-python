"""Unit tests for osw.service.ops.entities (Operation.fn called directly).

Importing ``osw.service.ops.entities`` registers its operations in
``osw.service.registry.REGISTRY`` at import time, so this module must not
clear the registry the way ``test_service_registry.py`` does.
"""

import copy
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


def test_create_or_update_entity_separates_created_from_updated(monkeypatch):
    """WtPage.exists is the pre-write value, so it tells the two apart.

    A caller that meant to update sees a create when it forgot to pass the
    stored uuid, which otherwise writes a second entity in silence.
    """
    osw = MagicMock()
    osw.fetch_schema.return_value = MagicMock(error_messages=[])
    osw.store_entity.return_value = MagicMock(
        pages={
            "Item:OSWnew": MagicMock(exists=False),
            "Item:OSWold": MagicMock(exists=True),
        },
        change_id="c1",
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

    assert result["created"] == ["Item:OSWnew"]
    assert result["updated"] == ["Item:OSWold"]
    assert result["skipped"] == []


def test_create_or_update_entity_reports_an_existing_page_as_skipped(monkeypatch):
    """'keep existing' leaves an existing page unwritten, which has to show.

    The operation returns its normal result either way, so without this the
    caller cannot tell a write from a no-op.
    """
    osw = MagicMock()
    osw.fetch_schema.return_value = MagicMock(error_messages=[])
    osw.store_entity.return_value = MagicMock(
        pages={"Item:OSWold": MagicMock(exists=True)}, change_id="c1"
    )
    monkeypatch.setattr(
        entities, "_resolve_category_class", lambda category: entities.model_entity.Item
    )
    monkeypatch.setattr(
        entities.config, "get_active_domain", lambda: "wiki-b.example.org"
    )
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.create_or_update_entity(
        ctx,
        category="Category:Item",
        jsondata={"label": [{"text": "Test"}]},
        overwrite="keep existing",
    )

    assert result["skipped"] == ["Item:OSWold"]
    assert result["updated"] == []
    assert result["created"] == []


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
def test_create_or_update_entity_records_created_and_updated_titles():
    op = registry.REGISTRY["create_or_update_entity"]

    result = {
        "titles": ["Item:OSW1", "Item:OSW2"],
        "created": ["Item:OSW1"],
        "updated": ["Item:OSW2"],
        "skipped": [],
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


def test_create_or_update_entity_does_not_record_a_skipped_page():
    """A skipped page was never written, so the ledger must not claim it.

    ``delete_entity`` trusts the ledger to decide whether a deletion needs the
    external-delete confirmation. A record for an unwritten page would drop
    that guard from a page this process never touched.
    """
    op = registry.REGISTRY["create_or_update_entity"]

    result = {
        "titles": ["Item:OSW1"],
        "created": [],
        "updated": [],
        "skipped": ["Item:OSW1"],
        "change_id": "c1",
        "urls": ["https://wiki.example.org/wiki/Item:OSW1"],
    }

    assert op.records(result) == []


def test_create_or_update_entity_records_empty_when_nothing_was_written():
    op = registry.REGISTRY["create_or_update_entity"]

    assert (
        op.records({
            "titles": [],
            "created": [],
            "updated": [],
            "skipped": [],
            "change_id": "c1",
            "urls": [],
        })
        == []
    )


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


# -- validate_entity -----------------------------------------------------------
def _stub_resolve_schema(monkeypatch, schema, sources=None, skipped=None):
    monkeypatch.setattr(
        entities,
        "_resolve_schema",
        lambda ctx, category: (schema, sources or [], skipped or []),
    )


def test_validate_entity_returns_valid_true_for_good_payload(monkeypatch):
    schema = {
        "type": "object",
        "properties": {"label": {"type": "string"}},
        "required": ["label"],
    }
    _stub_resolve_schema(monkeypatch, schema, sources=["Category:Item"])
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.validate_entity(
        ctx, category="Category:Item", jsondata={"label": "Test"}
    )

    assert result["category"] == "Category:Item"
    assert result["valid"] is True
    assert result["errors"] == []
    assert result["unknown_fields"] == []
    assert result["sources"] == ["Category:Item"]
    assert result["skipped"] == []


def test_validate_entity_includes_skipped_from_resolve_schema(monkeypatch):
    schema = {
        "type": "object",
        "properties": {"label": {"type": "string"}},
    }
    _stub_resolve_schema(
        monkeypatch,
        schema,
        sources=["Category:Item"],
        skipped=[{"title": "Category:Missing", "reason": "page does not exist"}],
    )
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.validate_entity(
        ctx, category="Category:Item", jsondata={"label": "Test"}
    )

    assert result["skipped"] == [
        {"title": "Category:Missing", "reason": "page does not exist"}
    ]


def test_validate_entity_returns_valid_false_for_missing_required_field(monkeypatch):
    schema = {
        "type": "object",
        "properties": {"label": {"type": "string"}},
        "required": ["label"],
    }
    _stub_resolve_schema(monkeypatch, schema)
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.validate_entity(ctx, category="Category:Item", jsondata={})

    assert result["valid"] is False
    assert result["errors"]


def test_validate_entity_reports_unknown_field_but_stays_valid(monkeypatch):
    schema = {"type": "object", "properties": {"label": {"type": "string"}}}
    _stub_resolve_schema(monkeypatch, schema)
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.validate_entity(
        ctx, category="Category:Item", jsondata={"label": "Test", "bogus_field": 1}
    )

    assert result["valid"] is True
    assert result["unknown_fields"] == ["bogus_field"]


def test_validate_entity_strips_remote_ref_and_lists_it_unchecked(monkeypatch):
    schema = {
        "type": "object",
        "properties": {
            "label": {"type": "string"},
            "parent": {
                "$ref": (
                    "https://wiki.example.org/wiki/Category:Parent"
                    "?action=raw&slot=jsonschema"
                )
            },
        },
    }
    _stub_resolve_schema(monkeypatch, schema)
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.validate_entity(
        ctx,
        category="Category:Item",
        jsondata={"label": "Test", "parent": {"anything": "goes"}},
    )

    assert result["valid"] is True
    assert result["unchecked_refs"] == ["$.properties.parent"]


def test_validate_entity_does_not_mutate_jsondata(monkeypatch):
    schema = {"type": "object", "properties": {"tags": {"type": "array"}}}
    _stub_resolve_schema(monkeypatch, schema)
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)
    jsondata = {"tags": ["a", "b"]}

    result = entities.validate_entity(ctx, category="Category:Item", jsondata=jsondata)

    assert result["valid"] is True
    assert jsondata == {"tags": ["a", "b"]}
    assert jsondata["tags"] == ["a", "b"]


def test_validate_entity_missing_category_raises_not_found():
    osw, _ = _osw_with_page(exists=False)
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.NotFound):
        entities.validate_entity(ctx, category="Category:Missing", jsondata={})


def test_validate_entity_malformed_schema_raises_schema_error(monkeypatch):
    # 'properties' must be non-empty so this trips the check_schema/
    # validator_for failure below, not the "no schema was read" guard above it
    # (FIX 1), which a bare {"type": 12345} would hit first.
    _stub_resolve_schema(
        monkeypatch, {"type": 12345, "properties": {"label": {"type": "string"}}}
    )
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.SchemaError):
        entities.validate_entity(ctx, category="Category:Item", jsondata={})


def test_validate_entity_collects_every_validation_error(monkeypatch):
    """A first-error-only implementation would satisfy a check that only
    asserts ``errors`` is truthy, so assert both specific messages appear."""
    schema = {
        "type": "object",
        "properties": {
            "label": {"type": "string"},
            "prio": {"type": "string"},
        },
        "required": ["label", "prio"],
    }
    _stub_resolve_schema(monkeypatch, schema)
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.validate_entity(ctx, category="Category:Item", jsondata={})

    assert result["valid"] is False
    joined = " ".join(result["errors"])
    assert "label" in joined
    assert "prio" in joined
    assert len(result["errors"]) == 2


def test_validate_entity_does_not_strip_a_local_ref(monkeypatch):
    schema = {
        "type": "object",
        "definitions": {"Name": {"type": "string"}},
        "properties": {
            "label": {"$ref": "#/definitions/Name"},
        },
    }
    _stub_resolve_schema(monkeypatch, schema)
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.validate_entity(
        ctx, category="Category:Item", jsondata={"label": 5}
    )

    # The $ref was followed (not stripped to {}), so the referenced
    # 'string' constraint is still enforced against the bad value.
    assert result["unchecked_refs"] == []
    assert result["valid"] is False
    assert result["errors"]


def test_validate_entity_unresolvable_local_ref_raises_schema_error(monkeypatch):
    """An unresolvable local $ref (no matching 'definitions' entry) makes
    iter_errors raise instead of yielding; FIX 3(b) must turn that into a
    SchemaError, not let it escape unmapped and not report valid: False."""
    schema = {
        "type": "object",
        "properties": {
            "label": {"$ref": "#/definitions/Missing"},
        },
    }
    _stub_resolve_schema(monkeypatch, schema)
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.SchemaError) as exc_info:
        entities.validate_entity(ctx, category="Category:Item", jsondata={"label": "x"})

    assert "Category:Item" in str(exc_info.value)


def test_validate_entity_end_to_end_via_mocked_page_reads():
    """Drives the merge-then-validate path through mocked page reads,
    instead of stubbing ``_resolve_schema`` like every other test here."""
    schema_dict = {
        "type": "object",
        "properties": {"label": {"type": "string"}},
        "required": ["label"],
    }
    page = MagicMock()
    page.exists = True
    page.get_slot_content.return_value = schema_dict
    osw = MagicMock()
    osw.site.get_page.return_value.pages = [page]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.validate_entity(
        ctx, category="Category:Item", jsondata={"label": "Test"}
    )

    assert result["valid"] is True
    assert result["sources"] == ["Category:Item"]


def test_validate_entity_raises_schema_error_when_category_has_no_schema_slot():
    """FIX 1: a category page that exists but has no 'jsonschema' slot must
    raise, not silently report 'valid: True' against an empty schema."""
    page = MagicMock()
    page.exists = True
    page.get_slot_content.return_value = None
    osw = MagicMock()
    osw.site.get_page.return_value.pages = [page]
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.SchemaError):
        entities.validate_entity(ctx, category="Category:Item", jsondata={})


def test_validate_entity_exempts_auto_filled_fields_from_required(monkeypatch):
    schema = {
        "type": "object",
        "properties": {
            "uuid": {"type": "string"},
            "label": {"type": "string"},
            "type": {"type": "array"},
        },
        "required": ["uuid", "label", "type"],
    }
    _stub_resolve_schema(monkeypatch, schema)
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.validate_entity(
        ctx, category="Category:Item", jsondata={"label": "Test"}
    )

    assert result["valid"] is True
    assert result["errors"] == []
    assert result["auto_filled"] == ["type", "uuid"]


def test_validate_entity_does_not_exempt_a_genuinely_required_field(monkeypatch):
    schema = {
        "type": "object",
        "properties": {
            "uuid": {"type": "string"},
            "label": {"type": "string"},
            "type": {"type": "array"},
        },
        "required": ["uuid", "label", "type"],
    }
    _stub_resolve_schema(monkeypatch, schema)
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.validate_entity(ctx, category="Category:Item", jsondata={})

    assert result["valid"] is False
    assert any("label" in err for err in result["errors"])
    assert result["auto_filled"] == ["type", "uuid"]


def test_validate_entity_auto_filled_is_empty_when_schema_has_no_required(
    monkeypatch,
):
    schema = {"type": "object", "properties": {"label": {"type": "string"}}}
    _stub_resolve_schema(monkeypatch, schema)
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.validate_entity(
        ctx, category="Category:Item", jsondata={"label": "Test"}
    )

    assert result["valid"] is True
    assert result["auto_filled"] == []


def test_auto_filled_fields_is_exactly_uuid_and_type():
    """A real assertion against the installed base model, not a stub: it
    fails loudly if the base model ever stops defaulting exactly these two,
    for example if a change widens or narrows the set."""
    assert entities._auto_filled_fields() == {"uuid", "type"}


def test_validate_entity_malformed_required_raises_schema_error_not_typeerror(
    monkeypatch,
):
    """An unhashable entry in 'required' (a nested list) must not blow up
    the auto_filled computation with a raw TypeError; it should reach
    check_schema and come back as the usual SchemaError."""
    schema = {
        "type": "object",
        "properties": {"label": {"type": "string"}},
        "required": ["label", ["nested"]],
    }
    _stub_resolve_schema(monkeypatch, schema)
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.SchemaError):
        entities.validate_entity(ctx, category="Category:Item", jsondata={})


def test_validate_entity_does_not_mutate_nested_required(monkeypatch):
    """Only the top-level 'required' list may be stripped of auto-filled
    fields; a 'required' nested inside a subschema is untouched."""
    schema = {
        "type": "object",
        "properties": {
            "label": {"type": "string"},
            "child": {
                "type": "object",
                "properties": {"uuid": {"type": "string"}},
                "required": ["uuid"],
            },
        },
        "required": ["label", "uuid"],
    }
    _stub_resolve_schema(monkeypatch, schema)
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.validate_entity(
        ctx,
        category="Category:Item",
        jsondata={"label": "Test", "child": {}},
    )

    assert result["auto_filled"] == ["uuid"]
    assert result["valid"] is False
    assert any("uuid" in err for err in result["errors"])


def test_validate_entity_does_not_mutate_resolved_schema(monkeypatch):
    """The dict _resolve_schema returned must come back unchanged; only the
    deep copy validate_entity builds from it may be modified."""
    schema = {
        "type": "object",
        "properties": {"uuid": {"type": "string"}, "label": {"type": "string"}},
        "required": ["uuid", "label"],
    }
    original = copy.deepcopy(schema)
    _stub_resolve_schema(monkeypatch, schema)
    osw, _ = _osw_with_page()
    ctx = Context(_settings(), Policy(), osw=osw)

    result = entities.validate_entity(
        ctx, category="Category:Item", jsondata={"label": "Test"}
    )

    assert result["valid"] is True
    assert schema == original


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


def test_delete_default_comment_carries_the_configured_log_prefix():
    osw, page = _osw_with_page()
    ledger = MagicMock()
    ledger.is_tracked.return_value = True
    ctx = Context(_settings(), Policy(), osw=osw, ledger=ledger)
    entities.config.set_log_prefix("osw-mcp")

    entities.delete_entity(ctx, title="Item:OSWx")

    page.delete.assert_called_once()
    assert page.delete.call_args[0][0].startswith("[osw-mcp]")
