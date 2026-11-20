"""Unit tests for the jsonschema slot regeneration in store_entity().

Regression guard for two defects in the schema aggregation of store_entity():

1. store_entity() passed the stored schema as `schema=`, a field that
   AggregateGeneratedSchemasParam does not have. Pydantic ignored it, so the
   aggregation always started from `{}` and every save dropped the hand-written
   part of the jsonschema slot.
2. In DEFINITIONS_SECTION mode the new generated schema was merged into the
   existing `$defs/generated` instead of replacing it, so a `required` entry or a
   `type` from an earlier save survived every regeneration.

The behaviour of the generation as a whole, and the cases ported from the wiki
form editor, are in tests/test_schema_generation_js_parity.py.

These run fully offline, see tests/schema_harness.py.
"""

import pytest

from tests.schema_harness import (
    GEN_POINTER,
    META_CATEGORY,
    category,
    characteristic,
    make_store,
)


@pytest.fixture
def store(monkeypatch):
    return make_store(monkeypatch)


def test_root_level_keeps_hand_written_schema(store):
    stored = {"title": "hand", "properties": {"manual": {"type": "string"}}}
    template = '{"title": "{{name}}", "properties": {"gen": {"type": "number"}}}'

    schema = store(category(), template, stored)

    assert schema["properties"]["manual"] == {"type": "string"}
    assert schema["properties"]["gen"] == {"type": "number"}
    assert schema["title"] == "TestCategory"


def test_definitions_section_keeps_hand_written_schema(store):
    stored = {"title": "hand", "$defs": {"manual": {"type": "string"}}}
    template = '{"title": "{{name}}", "type": "object"}'

    schema = store(characteristic(), template, stored)

    assert schema["$defs"]["manual"] == {"type": "string"}
    assert schema["$defs"]["generated"]["type"] == "object"
    assert schema["allOf"] == [{"$ref": GEN_POINTER}]


def test_definitions_section_replaces_stale_generated_section(store):
    stored = {"title": "hand", "$defs": {"manual": {"type": "string"}}}
    first_template = (
        '{"title": "{{name}}", "type": "object", "required": ["type"],'
        ' "properties": {"type": {"type": "string"}}}'
    )
    second_template = (
        '{"title": "{{name}}", "properties": {"value": {"type": "number"}}}'
    )

    first = store(characteristic(), first_template, stored)
    assert first["$defs"]["generated"]["required"] == ["type"]

    second = store(characteristic(), second_template, first)

    generated = second["$defs"]["generated"]
    assert "required" not in generated
    assert "type" not in generated
    assert "type" not in generated["properties"]
    assert generated["properties"]["value"] == {"type": "number"}
    assert generated["$comment"].count(META_CATEGORY) == 1
    assert second["allOf"] == [{"$ref": GEN_POINTER}]
    assert second["$defs"]["manual"] == {"type": "string"}


def test_failed_generation_keeps_generated_section(store):
    stored = {
        "title": "hand",
        "allOf": [{"$ref": GEN_POINTER}],
        "$defs": {"generated": {"type": "object", "required": ["type"]}},
    }
    # not valid JSON, so generation fails and produces no generated schema
    template = '{"title": {{name}}'

    schema = store(characteristic(), template, stored)

    assert schema == stored


def test_root_level_second_save_does_not_duplicate(store):
    stored = {"title": "hand", "properties": {"manual": {"type": "string"}}}
    template = (
        '{"title": "{{name}}", "required": ["gen"],'
        ' "properties": {"gen": {"type": "number"}}}'
    )

    first = store(category(), template, stored)
    second = store(category(), template, first)

    assert second == first
    assert second["required"] == ["gen"]
