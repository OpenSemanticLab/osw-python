"""Unit tests for WtSite.get_jsonld_context and WtSite.get_smw_property_map.

These tests construct a WtSite without going through ``__init__`` (which would
require network / credentials) and monkeypatch ``get_page`` to serve four
canned schemas modelling the real Task -> Process -> Item -> Entity category
chain, so the parent-chain resolution and its caches can be exercised without
a live wiki.
"""

import logging
import types

from osw.wtsite import WtSite

CATEGORY_TASK = "Category:Task"
CATEGORY_PROCESS = "Category:Process"
CATEGORY_ITEM = "Category:Item"
CATEGORY_ENTITY = "Category:Entity"


def _ref(title: str) -> str:
    """A parent reference URL, of the shape used in a real @context entry."""
    return f"/wiki/{title}?action=raw&slot=jsonschema"


# Entity contributes the root mappings: label (plain -> skos, starred ->
# Property:HasLabel, per the <key>* convention), an external-only field with
# no starred variant, and a prefix declaration.
ENTITY_SCHEMA = {
    "@context": [
        {
            "label": {"@id": "skos:prefLabel"},
            "label*": {"@id": "Property:HasLabel"},
            "description": {"@id": "schema:description"},
            "Property": {"@id": "wiki:Property-3A", "@prefix": True},
        }
    ]
}

# Item contributes its own field, plus a "status" mapping that its child
# Process overrides.
ITEM_SCHEMA = {
    "@context": [
        _ref(CATEGORY_ENTITY),
        {
            "icon": {"@id": "Property:HasIcon"},
            "status": {"@id": "Property:ItemStatus"},
        },
    ]
}

# Process contributes status (overriding Item's) and actionees.
PROCESS_SCHEMA = {
    "@context": [
        _ref(CATEGORY_ITEM),
        {
            "status": {"@id": "Property:HasStatus"},
            "actionees": {"@id": "Property:HasActionee"},
        },
    ]
}

# Task contributes prio and related_to.
TASK_SCHEMA = {
    "@context": [
        _ref(CATEGORY_PROCESS),
        {
            "prio": {"@id": "Property:HasPriority"},
            "related_to": {"@id": "Property:IsRelatedTo"},
        },
    ]
}

DEFAULT_PAGES = {
    CATEGORY_TASK: TASK_SCHEMA,
    CATEGORY_PROCESS: PROCESS_SCHEMA,
    CATEGORY_ITEM: ITEM_SCHEMA,
    CATEGORY_ENTITY: ENTITY_SCHEMA,
}


class _FakePage:
    def __init__(self, exists: bool, jsonschema, expected_slot: str = "jsonschema"):
        self.exists = exists
        self._jsonschema = jsonschema
        self._expected_slot = expected_slot

    def get_slot_content(self, slot_key, clone: bool = True):
        # A ``JsonSchema:`` page keeps its schema in the ``main`` slot, not
        # ``jsonschema``; fail loudly if the wrong slot is requested instead
        # of silently returning no mappings.
        assert slot_key == self._expected_slot
        return self._jsonschema


def _make_site(pages: dict):
    """A minimal WtSite, bypassing __init__, whose get_page is monkeypatched
    to serve ``pages`` (title -> schema dict). Returns the site and the list
    of titles requested, in request order, so a test can assert on the read
    count.
    """
    site = WtSite.__new__(WtSite)
    site._jsonld_context_cache = {}
    site._jsonld_page_context_cache = {}
    site._site = types.SimpleNamespace(host="wiki.example.org")

    requested_titles = []

    def fake_get_page(param):
        title = param.titles[0]
        requested_titles.append(title)
        schema = pages.get(title)
        expected_slot = "main" if title.startswith("JsonSchema:") else "jsonschema"
        page = _FakePage(
            exists=schema is not None, jsonschema=schema, expected_slot=expected_slot
        )
        return types.SimpleNamespace(pages=[page])

    site.get_page = fake_get_page
    return site, requested_titles


def test_merged_context_contains_mappings_from_every_level():
    site, _ = _make_site(DEFAULT_PAGES)

    context = site.get_jsonld_context(CATEGORY_TASK)

    assert "label" in context  # Entity
    assert "icon" in context  # Item
    assert "actionees" in context  # Process
    assert "prio" in context  # Task


def test_get_smw_property_map_derives_expected_names():
    site, _ = _make_site(DEFAULT_PAGES)

    props = site.get_smw_property_map(CATEGORY_TASK)

    assert props["status"] == "HasStatus"
    assert props["prio"] == "HasPriority"
    assert props["related_to"] == "IsRelatedTo"
    assert props["actionees"] == "HasActionee"
    # The starred key wins over the plain skos:prefLabel mapping.
    assert props["label"] == "HasLabel"


def test_external_vocabulary_only_field_is_excluded():
    site, _ = _make_site(DEFAULT_PAGES)

    context = site.get_jsonld_context(CATEGORY_TASK)
    props = site.get_smw_property_map(CATEGORY_TASK)

    assert context["description"] == {"@id": "schema:description"}
    assert "description" not in props


def test_prefix_declaration_is_excluded_from_the_property_map():
    site, _ = _make_site(DEFAULT_PAGES)

    props = site.get_smw_property_map(CATEGORY_TASK)

    assert "Property" not in props


def test_child_mapping_overrides_parent_mapping():
    site, _ = _make_site(DEFAULT_PAGES)

    props = site.get_smw_property_map(CATEGORY_TASK)

    # Item declares status -> Property:ItemStatus; its child Process
    # overrides it with status -> Property:HasStatus.
    assert props["status"] == "HasStatus"


def test_chain_is_read_once_per_page():
    site, requested_titles = _make_site(DEFAULT_PAGES)

    site.get_jsonld_context(CATEGORY_TASK)
    assert sorted(requested_titles) == sorted(DEFAULT_PAGES.keys())
    count_after_first = len(requested_titles)

    # Force the merge to run again by clearing only the top-level cache; the
    # per-page cache must still stop a second read of each page.
    site._jsonld_context_cache.clear()
    site.get_jsonld_context(CATEGORY_TASK)
    site._jsonld_context_cache.clear()
    site.get_jsonld_context(CATEGORY_TASK)

    assert len(requested_titles) == count_after_first


def test_returned_context_is_a_copy():
    site, _ = _make_site(DEFAULT_PAGES)

    first = site.get_jsonld_context(CATEGORY_TASK)
    first["mutated"] = "should not leak"
    first["label"] = "mutated"

    second = site.get_jsonld_context(CATEGORY_TASK)

    assert "mutated" not in second
    assert second["label"] != "mutated"


def test_cycle_terminates_and_merges_both_sides():
    cyclic_pages = {
        "Category:CycleA": {
            "@context": [
                _ref("Category:CycleB"),
                {"a_field": {"@id": "Property:HasA"}},
            ]
        },
        "Category:CycleB": {
            "@context": [
                _ref("Category:CycleA"),
                {"b_field": {"@id": "Property:HasB"}},
            ]
        },
    }
    site, _ = _make_site(cyclic_pages)

    context = site.get_jsonld_context("Category:CycleA")

    assert context["a_field"] == {"@id": "Property:HasA"}
    assert context["b_field"] == {"@id": "Property:HasB"}


def test_missing_page_contributes_nothing_and_does_not_raise():
    site, _ = _make_site(DEFAULT_PAGES)

    context = site.get_jsonld_context("Category:DoesNotExist")

    assert context == {}


def test_jsonschema_parent_is_read_from_the_main_slot():
    """A ``JsonSchema:`` parent keeps its schema in the ``main`` slot, not
    ``jsonschema``. ``_make_site``'s fake fails the test outright if the
    wrong slot is requested."""
    pages = dict(DEFAULT_PAGES)
    pages["Category:WithJsonSchemaParent"] = {
        "@context": [
            _ref("JsonSchema:Shared"),
            {"tag": {"@id": "Property:HasTag"}},
        ]
    }
    pages["JsonSchema:Shared"] = {
        "@context": [{"shared_field": {"@id": "Property:HasShared"}}]
    }
    site, _ = _make_site(pages)

    context = site.get_jsonld_context("Category:WithJsonSchemaParent")

    assert context["tag"] == {"@id": "Property:HasTag"}
    assert context["shared_field"] == {"@id": "Property:HasShared"}


def test_page_read_failure_is_warned_about_and_cached(caplog):
    """A page read that raises must not be repeated: get_page retries 5 times
    with sleep(5) in between before it raises, so a wiki that cannot serve a
    schema page would otherwise pay that delay again on every call."""
    calls = []

    def flaky_get_page(param):
        title = param.titles[0]
        calls.append(title)
        if title == CATEGORY_ITEM:
            raise RuntimeError("network down")
        schema = DEFAULT_PAGES.get(title)
        page = _FakePage(exists=schema is not None, jsonschema=schema)
        return types.SimpleNamespace(pages=[page])

    site = WtSite.__new__(WtSite)
    site._jsonld_context_cache = {}
    site._jsonld_page_context_cache = {}
    site._site = types.SimpleNamespace(host="wiki.example.org")
    site.get_page = flaky_get_page

    with caplog.at_level(logging.WARNING, logger="osw.wtsite"):
        context = site.get_jsonld_context(CATEGORY_TASK)
    assert CATEGORY_ITEM in caplog.text

    # Item's own mapping, and everything above it (Entity's), is lost.
    assert "icon" not in context
    assert "label" not in context
    # Process and Task, which do not depend on a successful Item read for
    # their own mappings, still contribute.
    assert "actionees" in context
    assert "prio" in context

    calls_after_first_run = len(calls)
    # Clear only the top-level cache, like test_chain_is_read_once_per_page,
    # so the merge runs again and exercises the per-page cache rather than
    # short-circuiting on the already-cached top-level result.
    site._jsonld_context_cache.clear()
    site.get_jsonld_context(CATEGORY_TASK)

    assert len(calls) == calls_after_first_run


def test_max_depth_is_part_of_the_cache_key():
    """A caller that first asks for a truncated depth must not receive the
    truncated result when it later asks for the (different) default depth."""
    site, _ = _make_site(DEFAULT_PAGES)

    truncated = site.get_jsonld_context(CATEGORY_TASK, max_depth=2)
    full = site.get_jsonld_context(CATEGORY_TASK)

    # Entity, three levels above Task, is out of reach at max_depth=2.
    assert "label" not in truncated
    assert "label" in full
