"""store_entity() must select category templates like the wiki form editor.

The fixtures are two real Category pages (PhysicalItem and PhysicalItemType) in
the slot state before and after an unchanged save through the form editor of the
dev wiki on 2026-11-05 (revisions 134604 and 134605). The form editor only added
"version": "0.1.0" to each jsondata.

The test stores the after-jsondata offline on top of the before-jsonschema and
expects the jsonschema the form editor wrote. The meta category pages come from
the package files in tests/fixtures/category_template_selection/meta, so no wiki
is read or written.
"""

import copy
import json
from pathlib import Path

import pytest
from opensemantic.core.v1 import Category

from osw.core import (
    OSW,
    collect_category_template_titles,
    reset_generated_jsonld_context,
    strip_root_members_superseded_by_generated,
)
from osw.wtsite import WtPage

FIXTURES = Path(__file__).parent / "fixtures" / "category_template_selection"
CHARACTERISTIC_TYPE = "Category:OSWffe74f291d354037b318c422591c5023"

# fixture file stem -> page title
META_PAGES = {
    "Category:Category": "Category",
    CHARACTERISTIC_TYPE: "CharacteristicType",
    "Category:Entity": "Entity",
}

PAGES = {
    "PhysicalItem": "Category:OSW37a57741ae2e4dd4b29b1172b6848be8",
    "PhysicalItemType": "Category:OSWca99a9bb9ad24386b222d18a73c2af5e",
}


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class _FakeMetaCategoryPage:
    def __init__(self, title, stem):
        self.title = title
        meta = FIXTURES / "meta"
        template_file = meta / f"{stem}.schema_template.txt"
        self._slots = {
            "jsondata": json.loads(
                (meta / f"{stem}.jsondata.json").read_text(encoding="utf-8")
            ),
            "jsonschema": json.loads(
                (meta / f"{stem}.jsonschema.json").read_text(encoding="utf-8")
            ),
            "schema_template": (
                template_file.read_text(encoding="utf-8")
                if template_file.exists()
                else None
            ),
        }

    def get_slot_content(self, slot_key):
        return self._slots.get(slot_key)


class _FakeGetPageResult:
    def __init__(self, pages):
        self.pages = pages


class _FakeSite:
    """Serves the meta category pages from the fixture files."""

    def __init__(self):
        self.requested = []

    def get_page(self, param):
        self.requested.extend(param.titles)
        return _FakeGetPageResult([
            _FakeMetaCategoryPage(t, META_PAGES[t]) for t in param.titles
        ])


def _store_offline(monkeypatch, jsondata, stored_schema):
    original_policy = OSW._apply_overwrite_policy

    def policy_with_stored_schema(param):
        param.page.set_slot_content("jsonschema", copy.deepcopy(stored_schema))
        return original_policy(param)

    monkeypatch.setattr(
        OSW, "_apply_overwrite_policy", staticmethod(policy_with_stored_schema)
    )
    site = _FakeSite()
    entity = Category(**copy.deepcopy(jsondata))
    result = OSW.construct(site=site).store_entity(
        OSW.StoreEntityParam(entities=[entity], namespace="Category", offline=True)
    )
    (page,) = result.pages.values()
    assert isinstance(page, WtPage)
    return page.get_slot_content("jsonschema"), site


@pytest.mark.parametrize("name", sorted(PAGES))
def test_store_matches_form_editor_save(monkeypatch, name):
    title = PAGES[name]
    before = _load("before-form-editor-save.json")[title]
    after = _load("after-form-editor-save.json")[title]

    schema, site = _store_offline(monkeypatch, after["jsondata"], before["jsonschema"])

    assert schema == after["jsonschema"]
    assert CHARACTERISTIC_TYPE in site.requested


@pytest.mark.parametrize("name", sorted(PAGES))
def test_generated_section_lists_both_templates(monkeypatch, name):
    title = PAGES[name]
    before = _load("before-form-editor-save.json")[title]
    after = _load("after-form-editor-save.json")[title]

    schema, _ = _store_offline(monkeypatch, after["jsondata"], before["jsonschema"])

    comment = schema["$defs"]["generated"]["$comment"]
    assert comment.endswith(f"Category:Category {CHARACTERISTIC_TYPE}")


def test_collect_follows_allof_in_wiki_order():
    schemas = {
        "Category:Category": {
            "uuid": "89aafe6d-ae5a-4f29-97ff-df7736d4cab6",
            "allOf": [
                {"$ref": f"/wiki/{CHARACTERISTIC_TYPE}?action=raw&slot=jsonschema"}
            ],
        },
        CHARACTERISTIC_TYPE: {
            "uuid": "ffe74f29-1d35-4037-b318-c422591c5023",
            "allOf": [{"$ref": "/wiki/Category:Entity?action=raw&slot=jsonschema"}],
        },
        "Category:Entity": {"uuid": "ce353767-c628-45bd-9d88-d6eb3009aec0"},
    }

    class Page:
        def __init__(self, title):
            self.title = title

        def get_slot_content(self, slot):
            return schemas[self.title]

    titles = collect_category_template_titles(
        lambda ts: [Page(t) for t in ts], ["Category:Category"]
    )

    assert titles == ["Category:Category", CHARACTERISTIC_TYPE]


def test_reset_context_keeps_manual_block_when_never_generated():
    schema = {"@context": ["/wiki/Category:A", {"manual": "x"}]}

    reset_generated_jsonld_context(schema, had_generated_section=False)

    assert schema["@context"] == ["/wiki/Category:A", {}, {"manual": "x"}]


def test_reset_context_empties_generated_block():
    schema = {"@context": ["/wiki/Category:A", {"gen": "x"}, {"manual": "y"}]}

    reset_generated_jsonld_context(schema, had_generated_section=True)

    assert schema["@context"] == ["/wiki/Category:A", {}, {"manual": "y"}]


def test_strip_keeps_manual_siblings():
    root = {
        "uuid": "u",
        "title": "t",
        "properties": {"type": {"default": ["x"], "minItems": 1}},
    }
    generated = {"uuid": "u", "properties": {"type": {"default": ["x"]}}}

    assert strip_root_members_superseded_by_generated(root, generated) is True
    assert root == {"title": "t", "properties": {"type": {"minItems": 1}}}


def test_collect_warns_when_a_schema_is_missing(caplog):
    class Page:
        title = "Category:Category"

        def get_slot_content(self, slot):
            return None

    with caplog.at_level("WARNING", logger="osw.core"):
        titles = collect_category_template_titles(
            lambda ts: [Page()], ["Category:Category"]
        )

    assert titles == ["Category:Category"]
    assert "No jsonschema found for Category:Category" in caplog.text


def test_collect_follows_properties_and_items_in_wiki_order():
    meta = "Category:OSW0a1b2c3d4e5f4a6b8c7d9e0f1a2b3c4d"
    prop_cat = "Category:OSW11111111222243338444555555555555"
    items_cat = "Category:OSW66666666777748889999aaaaaaaaaaaa"

    def ref(title):
        return {"$ref": f"/wiki/{title}?action=raw&slot=jsonschema"}

    schemas = {
        meta: {
            "uuid": "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
            "allOf": [ref(CHARACTERISTIC_TYPE)],
            "properties": {
                "first": ref(prop_cat),
                "list": {"type": "array", "items": ref(items_cat)},
                # the second reference to a bundled schema is not walked again
                "again": ref(prop_cat),
            },
        },
        CHARACTERISTIC_TYPE: {"uuid": "ffe74f29-1d35-4037-b318-c422591c5023"},
        prop_cat: {"uuid": "11111111-2222-4333-8444-555555555555"},
        items_cat: {"uuid": "66666666-7777-4888-9999-aaaaaaaaaaaa"},
    }
    requested = []

    class Page:
        def __init__(self, title):
            self.title = title

        def get_slot_content(self, slot):
            return schemas[self.title]

    def get_pages(titles):
        requested.extend(titles)
        return [Page(t) for t in titles]

    titles = collect_category_template_titles(get_pages, [meta])

    # allOf first, then properties in their order, then the uuid of the node itself
    assert titles == [
        "Category:Category",
        CHARACTERISTIC_TYPE,
        prop_cat,
        items_cat,
        meta,
    ]
    assert requested.count(prop_cat) == 1
