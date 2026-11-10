"""Unit tests for the jsonschema slot regeneration in store_entity().

Regression guard for two defects in the schema aggregation of store_entity():

1. store_entity() passed the stored schema as `schema=`, a field that
   AggregateGeneratedSchemasParam does not have. Pydantic ignored it, so the
   aggregation always started from `{}` and every save dropped the hand-written
   part of the jsonschema slot.
2. In DEFINITIONS_SECTION mode the new generated schema was merged into the
   existing `$defs/generated` instead of replacing it, so a `required` entry or a
   `type` from an earlier save survived every regeneration.

These run fully offline: store_entity() runs with offline=True, the meta category
is served by a fake site and the overwrite policy is wrapped to put a stored
jsonschema slot on the page, so no network is required.
"""

import json

import pytest
from opensemantic.core.v1 import CharacteristicType

import osw.model.entity as model
from osw.core import OSW
from osw.wtsite import WtPage

META_UUID = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
META_CATEGORY = "Category:OSW0a1b2c3d4e5f4a6b8c7d9e0f1a2b3c4d"
CHARACTERISTIC_TYPE = "Category:OSWffe74f291d354037b318c422591c5023"
GEN_POINTER = "#/$defs/generated"


class _FakeMetaCategoryPage:
    def __init__(self, title, template, schema):
        self.title = title
        self._slots = {
            "schema_template": template,
            "jsondata": {},
            "jsonschema": schema,
        }

    def get_slot_content(self, slot_key):
        return self._slots[slot_key]


class _FakeGetPageResult:
    def __init__(self, pages):
        self.pages = pages


class _FakeSite:
    """Serves a meta category with the template under test.

    Like in the wiki, the templates follow the allOf chain of the meta category
    schema, so the meta category refers to CharacteristicType when `definitions`
    is set.
    """

    def __init__(self, template, definitions):
        self.template = template
        self.definitions = definitions

    def _page(self, title):
        if title == META_CATEGORY:
            schema = {"uuid": META_UUID}
            if self.definitions:
                schema["allOf"] = [
                    {"$ref": f"/wiki/{CHARACTERISTIC_TYPE}?action=raw&slot=jsonschema"}
                ]
            return _FakeMetaCategoryPage(title, self.template, schema)
        if title == CHARACTERISTIC_TYPE:
            return _FakeMetaCategoryPage(
                title, None, {"uuid": "ffe74f29-1d35-4037-b318-c422591c5023"}
            )
        return _FakeMetaCategoryPage(title, None, {})

    def get_page(self, param):
        return _FakeGetPageResult([self._page(t) for t in param.titles])


@pytest.fixture
def store(monkeypatch):
    """Runs store_entity() offline on a page whose jsonschema slot holds `stored`.

    Returns the jsonschema slot that store_entity() wrote.
    """
    original_policy = OSW._apply_overwrite_policy

    def _store(entity, template, stored, definitions=None):
        if definitions is None:
            # characteristics select the definitions section mode in the wiki
            definitions = isinstance(entity, CharacteristicType)

        def policy_with_stored_schema(param):
            if stored is not None:
                param.page.set_slot_content(
                    "jsonschema", json.loads(json.dumps(stored))
                )
            return original_policy(param)

        monkeypatch.setattr(
            OSW, "_apply_overwrite_policy", staticmethod(policy_with_stored_schema)
        )
        osw_obj = OSW.construct(site=_FakeSite(template, definitions))
        result = osw_obj.store_entity(
            OSW.StoreEntityParam(
                entities=[entity],
                namespace="Category",
                meta_category_title=META_CATEGORY,
                offline=True,
            )
        )
        (page,) = result.pages.values()
        assert isinstance(page, WtPage)
        return page.get_slot_content("jsonschema")

    return _store


def _characteristic():
    return CharacteristicType(
        uuid="efad8086-4a76-47ca-b278-f5f944e5754b",
        name="TestCharacteristic",
        label=[{"text": "Test Characteristic"}],
        # the default resolves a superclass from a wiki
        subclass_of=[],
    )


def _category():
    # store_entity() selects ROOT_LEVEL mode for any entity that is not a
    # characteristic, so a plain Item stored in the Category namespace suffices
    return model.Item(
        uuid="0d0c1c35-4c4d-4e3a-9c9a-6f4a1b2c3d4e",
        name="TestCategory",
        label=[model.Label(text="Test Category")],
    )


def test_root_level_keeps_hand_written_schema(store):
    stored = {"title": "hand", "properties": {"manual": {"type": "string"}}}
    template = '{"title": "{{name}}", "properties": {"gen": {"type": "number"}}}'

    schema = store(_category(), template, stored)

    assert schema["properties"]["manual"] == {"type": "string"}
    assert schema["properties"]["gen"] == {"type": "number"}
    assert schema["title"] == "TestCategory"


def test_definitions_section_keeps_hand_written_schema(store):
    stored = {"title": "hand", "$defs": {"manual": {"type": "string"}}}
    template = '{"title": "{{name}}", "type": "object"}'

    schema = store(_characteristic(), template, stored)

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

    first = store(_characteristic(), first_template, stored)
    assert first["$defs"]["generated"]["required"] == ["type"]

    second = store(_characteristic(), second_template, first)

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

    schema = store(_characteristic(), template, stored)

    assert schema == stored


def test_root_level_second_save_does_not_duplicate(store):
    stored = {"title": "hand", "properties": {"manual": {"type": "string"}}}
    template = (
        '{"title": "{{name}}", "required": ["gen"],'
        ' "properties": {"gen": {"type": "number"}}}'
    )

    first = store(_category(), template, stored)
    second = store(_category(), template, first)

    assert second == first
    assert second["required"] == ["gen"]
