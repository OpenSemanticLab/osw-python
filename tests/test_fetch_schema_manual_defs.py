"""Tests for flattening `$defs/manual` before code generation in fetch_schema.

Hand-authored schema pages keep their schema in `$defs/manual`. Like
`$defs/generated`, it has to be merged into the schema root, otherwise
datamodel-code-generator cannot resolve a `$ref` to such a page that has
additional keys next to it. Fully offline.
"""

import osw.core as osw_core
from osw.core import OSW, _flatten_manual_definitions
from osw.wtsite import WtPage


def ref(title):
    return f"/wiki/Category:{title}?action=raw&slot=jsonschema"


class OfflineSite:
    def get_cache_enabled(self):
        return False

    def enable_cache(self):
        pass

    def disable_cache(self):
        pass

    def get_page(self, *args, **kwargs):
        raise AssertionError("online fetch attempted")


def fetch_offline(schemas, monkeypatch, tmp_path):
    pages = {}
    for name, schema in schemas.items():
        page = WtPage(title=f"Category:{name}", do_init=False)
        page.exists = True
        page.set_slot_content("jsonschema", schema)
        pages[f"Category:{name}"] = page
    monkeypatch.setattr(osw_core, "get_model_dir_path", lambda: str(tmp_path))
    return OSW.construct(site=OfflineSite()).fetch_schema(
        OSW.FetchSchemaParam(
            schema_title="Category:Test", mode="replace", offline_pages=pages
        )
    )


def test_item_via_defs_manual_with_extra_key_beside_ref(monkeypatch, tmp_path):
    schemas = {
        "Item": {
            "allOf": [{"$ref": "#/$defs/manual"}],
            "$defs": {"manual": {"type": "string"}},
        },
        "Test": {
            "type": "object",
            "title": "Test",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"title*": {"en": "x"}, "$ref": ref("Item")},
                }
            },
        },
    }
    fetch_offline(schemas, monkeypatch, tmp_path)


def test_hand_authored_shape_with_generated_pointing_to_manual(monkeypatch, tmp_path):
    schemas = {
        "WikiFile": {
            "allOf": [{"$ref": "#/$defs/generated"}],
            "title": "WikiFile",
            "$defs": {
                "generated": {
                    "allOf": [{"$ref": "#/$defs/manual"}],
                    "uuid": "00000000-0000-4000-8000-000000000001",
                    "title": "WikiFile",
                    "title*": {"en": "Wiki File"},
                },
                "manual": {"type": "string", "anyOf": [{"pattern": "^File:.*"}]},
            },
        },
        "Test": {
            "type": "object",
            "title": "Test",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"title*": {"en": "x"}, "$ref": ref("WikiFile")},
                }
            },
        },
    }
    fetch_offline(schemas, monkeypatch, tmp_path)


def test_object_rooted_manual_used_as_allof_mixin(monkeypatch, tmp_path):
    schemas = {
        "Mixin": {
            "allOf": [{"$ref": "#/$defs/manual"}],
            "$defs": {
                "manual": {
                    "type": "object",
                    "title": "Mixin",
                    "properties": {
                        "values": {
                            "type": "array",
                            "items": {"title*": {"en": "x"}, "$ref": ref("Item")},
                        }
                    },
                }
            },
        },
        "Item": {
            "allOf": [{"$ref": "#/$defs/manual"}],
            "$defs": {"manual": {"type": "string"}},
        },
        "Test": {"type": "object", "title": "Test", "allOf": [{"$ref": ref("Mixin")}]},
    }
    fetch_offline(schemas, monkeypatch, tmp_path)


def test_helper_root_ref_form():
    schema = {
        "$ref": "#/$defs/manual",
        "$defs": {"manual": {"type": "string"}},
    }
    assert _flatten_manual_definitions(schema) == {"type": "string"}


def test_helper_allof_form():
    schema = {
        "allOf": [{"$ref": "#/$defs/manual"}, {"$ref": "/wiki/Category:Other"}],
        "$defs": {
            "manual": {"type": "object", "properties": {"a": {"type": "string"}}}
        },
    }
    assert _flatten_manual_definitions(schema) == {
        "allOf": [{"$ref": "/wiki/Category:Other"}],
        "type": "object",
        "properties": {"a": {"type": "string"}},
    }


def test_helper_keeps_other_defs():
    schema = {
        "allOf": [{"$ref": "#/$defs/manual"}],
        "$defs": {"manual": {"type": "string"}, "other": {"type": "number"}},
    }
    assert _flatten_manual_definitions(schema) == {
        "type": "string",
        "$defs": {"other": {"type": "number"}},
    }


def test_helper_unreferenced_manual_unchanged():
    schema = {"title": "T", "$defs": {"manual": {"type": "string"}}}
    expected = {"title": "T", "$defs": {"manual": {"type": "string"}}}
    assert _flatten_manual_definitions(schema) == expected


def test_helper_preserves_root_pointer_inside_manual():
    schema = {
        "allOf": [{"$ref": "#/$defs/manual"}],
        "$defs": {
            "manual": {
                "type": "object",
                "properties": {"child": {"$ref": "#"}},
            }
        },
    }
    result = _flatten_manual_definitions(schema)
    assert result["properties"]["child"] == {"$ref": "#"}


def test_helper_root_keys_win_over_manual_keys():
    schema = {
        "title": "Root",
        "allOf": [{"$ref": "#/$defs/manual"}],
        "$defs": {"manual": {"title": "Manual", "type": "string"}},
    }
    result = _flatten_manual_definitions(schema)
    assert result["title"] == "Root"
    assert result["type"] == "string"
    assert "$defs" not in result


def test_helper_root_ref_and_allof_entry_both_removed():
    schema = {
        "$ref": "#/$defs/manual",
        "allOf": [{"$ref": "#/$defs/manual"}],
        "$defs": {"manual": {"type": "string"}},
    }
    result = _flatten_manual_definitions(schema)
    assert result == {"type": "string"}


def test_helper_two_allof_entries_both_removed():
    schema = {
        "allOf": [{"$ref": "#/$defs/manual"}, {"$ref": "#/$defs/manual"}],
        "$defs": {"manual": {"type": "string"}},
    }
    result = _flatten_manual_definitions(schema)
    assert "#/$defs/manual" not in str(result)
    assert result == {"type": "string"}
