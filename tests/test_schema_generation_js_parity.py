"""Reference cases of the schema generation, ported from the wiki form editor.

store_entity() regenerates the jsonschema slot of a Category page the same way
the form editor does on save. The reference implementation is
osl.util.postProcessPage in PageBot.js of
mediawiki-extensions-OpenSemanticLab:
https://github.com/OpenSemanticLab/mediawiki-extensions-OpenSemanticLab/blob/e19619c/modules/ext.OpenSemanticLab.forms/PageBot.js#L375-L757

Each test below names the reference behaviour it pins. The known deviations are
pinned as well, so that a change to them is a deliberate one.
"""

import pytest

from osw.core import (
    AddOverwriteClassOptions,
    merge_generated_jsonld_context,
    remove_generated_schema_section,
    reset_generated_jsonld_context,
    strip_root_members_superseded_by_generated,
)
from tests.schema_harness import (
    GEN_POINTER,
    category,
    characteristic,
    make_store,
)


@pytest.fixture
def store(monkeypatch):
    return make_store(monkeypatch)


# ---------------------------------------------------------------------------
# remove_generated_schema_section: the "reset generated content" block
# ---------------------------------------------------------------------------


def test_remove_generated_section_drops_section_and_allof_pointer():
    schema = {
        "title": "hand",
        "allOf": [{"$ref": "/wiki/Category:Parent?action=raw"}, {"$ref": GEN_POINTER}],
        "$defs": {"generated": {"type": "object"}, "manual": {"type": "string"}},
    }

    remove_generated_schema_section(schema)

    assert "generated" not in schema["$defs"]
    assert schema["$defs"]["manual"] == {"type": "string"}
    assert schema["allOf"] == [{"$ref": "/wiki/Category:Parent?action=raw"}]


def test_remove_generated_section_drops_root_ref_pointer():
    """generate_root_ref=True puts the pointer in the root $ref, not in allOf.

    PageBot.js removes that form too. Leaving it behind pointed the schema at a
    $defs entry that had just been deleted.
    """
    schema = {"$ref": GEN_POINTER, "$defs": {"generated": {"type": "object"}}}

    remove_generated_schema_section(schema)

    assert "$ref" not in schema
    assert "generated" not in schema["$defs"]


def test_remove_generated_section_keeps_a_foreign_root_ref():
    schema = {"$ref": "#/$defs/manual", "$defs": {"generated": {}, "manual": {}}}

    remove_generated_schema_section(schema)

    assert schema["$ref"] == "#/$defs/manual"


@pytest.mark.parametrize("stored", ["a string", ["a", "list"], 5])
def test_remove_generated_section_tolerates_a_non_dict_slot(stored):
    """A jsonschema slot is not guaranteed to hold an object.

    get_slot_content() returns whatever the slot holds, and a slot stored with a
    non-json content model gives a string. Raising here aborted the whole
    store_entity() call.
    """
    assert remove_generated_schema_section(stored) == stored


def test_remove_generated_section_uses_the_given_keys():
    schema = {"defs": {"gen": {}}, "allOf": [{"$ref": "#/defs/gen"}]}

    remove_generated_schema_section(schema, def_key="defs", gen_def_key="gen")

    assert schema["defs"] == {}
    assert schema["allOf"] == []


# ---------------------------------------------------------------------------
# reset_generated_jsonld_context
# ---------------------------------------------------------------------------


def test_reset_context_empties_the_generated_block_in_place():
    schema = {"@context": ["/wiki/Category:Parent?action=raw", {"v": "ex:v"}]}

    reset_generated_jsonld_context(schema, had_generated_section=True)

    assert schema["@context"] == ["/wiki/Category:Parent?action=raw", {}]


def test_reset_context_reserves_a_block_before_a_hand_written_one():
    """Without a previous generated section the first object block is manual.

    Emptying it would delete hand written mappings, so an empty block is
    inserted ahead of it to take the generated mappings.
    """
    schema = {"@context": ["/wiki/Category:Parent?action=raw", {"manual": "ex:m"}]}

    reset_generated_jsonld_context(schema, had_generated_section=False)

    assert schema["@context"] == [
        "/wiki/Category:Parent?action=raw",
        {},
        {"manual": "ex:m"},
    ]


def test_reset_context_appends_a_block_when_there_is_none():
    schema = {"@context": ["/wiki/Category:Parent?action=raw"]}

    reset_generated_jsonld_context(schema, had_generated_section=True)

    assert schema["@context"] == ["/wiki/Category:Parent?action=raw", {}]


@pytest.mark.parametrize("context", ["/wiki/Category:Parent?action=raw", {"v": "ex:v"}])
def test_reset_context_leaves_a_string_or_object_context(context):
    """Only the array form carries a generated block by convention."""
    schema = {"@context": context}

    reset_generated_jsonld_context(schema, had_generated_section=True)

    assert schema["@context"] == context


def test_reset_context_tolerates_an_empty_schema():
    reset_generated_jsonld_context(None, had_generated_section=True)
    reset_generated_jsonld_context({}, had_generated_section=True)


# ---------------------------------------------------------------------------
# merge_generated_jsonld_context
# ---------------------------------------------------------------------------


def test_merge_context_fills_only_the_reserved_block():
    """A manual block placed after the generated one must stay separate.

    oold's aggregate_generated_schemas() collapses every object entry into one,
    which fused the two. The next reset would then delete the manual mappings
    along with the generated ones.
    """
    schema = {"@context": ["/wiki/Category:Parent?action=raw", {}, {"manual": "ex:m"}]}

    merge_generated_jsonld_context(schema, [{"gen": "ex:g"}])

    assert schema["@context"] == [
        "/wiki/Category:Parent?action=raw",
        {"gen": "ex:g"},
        {"manual": "ex:m"},
    ]


def test_merge_context_appends_a_new_parent_reference_once():
    schema = {"@context": ["/wiki/Category:P1?action=raw", {}]}

    merge_generated_jsonld_context(
        schema, ["/wiki/Category:P1?action=raw", "/wiki/Category:P2?action=raw", {}]
    )

    assert schema["@context"].count("/wiki/Category:P1?action=raw") == 1
    assert "/wiki/Category:P2?action=raw" in schema["@context"]


def test_reset_and_merge_drop_the_mappings_of_a_former_parent():
    """The reference case: a Characteristic whose parent changes.

    The term mappings of the old parent must not survive, or JSON-LD expansion
    keeps using terms of a superclass the Category no longer declares.
    """
    schema = {"@context": ["/wiki/Category:P1?action=raw", {"v": "ex:v"}]}

    reset_generated_jsonld_context(schema, had_generated_section=True)
    merge_generated_jsonld_context(
        schema, ["/wiki/Category:P2?action=raw", {"w": "ex:w"}]
    )

    (block,) = [e for e in schema["@context"] if isinstance(e, dict)]
    assert block == {"w": "ex:w"}


def test_reset_and_merge_keep_the_reference_of_a_former_parent():
    """Known deviation, shared with the form editor.

    The string entries of @context are parent schema references. They carry no
    marker that tells a stale generated one from a hand written one, so the
    reference of a removed superclass stays in the list. Only the term mappings
    are rebuilt. Removing the stale reference needs a record of what the last
    generation wrote.
    """
    schema = {"@context": ["/wiki/Category:P1?action=raw", {"v": "ex:v"}]}

    reset_generated_jsonld_context(schema, had_generated_section=True)
    merge_generated_jsonld_context(
        schema, ["/wiki/Category:P2?action=raw", {"w": "ex:w"}]
    )

    assert "/wiki/Category:P1?action=raw" in schema["@context"]


# ---------------------------------------------------------------------------
# strip_root_members_superseded_by_generated
# ---------------------------------------------------------------------------


def test_strip_retires_a_root_copy_but_keeps_manual_siblings():
    """The reference case from PageBot.js: a copied category.

    A member at root takes precedence over the same member pulled in through
    allOf, so the root copy of 'default' typed instances as the source category.
    The siblings on the same object are hand written and have to survive.
    """
    root = {
        "properties": {
            "type": {
                "default": ["Category:Source"],
                "items": {"type": "string"},
                "minItems": 1,
            }
        }
    }
    generated = {"properties": {"type": {"default": ["Category:Copy"]}}}

    assert strip_root_members_superseded_by_generated(root, generated) is True
    assert root["properties"]["type"] == {"items": {"type": "string"}, "minItems": 1}


def test_strip_drops_a_container_that_only_held_generated_members():
    root = {"properties": {"gen": {"type": "number"}}}
    generated = {"properties": {"gen": {"type": "number"}}}

    strip_root_members_superseded_by_generated(root, generated)

    assert "properties" not in root


def test_strip_skips_the_members_promoted_to_root():
    root = {
        "title": "Root title",
        "description": "Root description",
        "$comment": "note",
        "@context": [{"v": "ex:v"}],
        "$defs": {"generated": {}},
        "$ref": "#/$defs/manual",
    }
    generated = {
        "title": "Generated title",
        "description": "Generated description",
        "$comment": "generated note",
        "@context": [{"v": "ex:v"}],
        "$defs": {},
        "$ref": "#/$defs/generated",
    }

    assert strip_root_members_superseded_by_generated(root, generated) is False
    assert root["title"] == "Root title"
    assert root["@context"] == [{"v": "ex:v"}]
    assert root["$ref"] == "#/$defs/manual"


def test_strip_removes_root_allof_refs_the_generated_section_repeats():
    """The generated section repeats the parent refs in its own allOf.

    Root listed them twice: directly and again through the generated section.
    """
    parent = {"$ref": "/wiki/Category:Parent?action=raw"}
    root = {"allOf": [parent, {"$ref": GEN_POINTER}]}
    generated = {"allOf": [parent]}

    assert strip_root_members_superseded_by_generated(root, generated) is True
    assert root["allOf"] == [{"$ref": GEN_POINTER}]


def test_strip_reports_nothing_removed_for_a_clean_schema():
    root = {"properties": {"manual": {"type": "string"}}}
    generated = {"properties": {"gen": {"type": "number"}}}

    assert strip_root_members_superseded_by_generated(root, generated) is False
    assert root["properties"]["manual"] == {"type": "string"}


# ---------------------------------------------------------------------------
# store_entity(): the generation as a whole
# ---------------------------------------------------------------------------


def test_partial_generation_failure_keeps_the_stored_schema(store):
    """One template renders, a later one fails: nothing may be written.

    The form editor aborts the save when any template fails. Writing the part
    that did render replaced the stored generated section with a fragment, so a
    transient failure of one template silently dropped the rest of the schema.
    """
    stored = {
        "title": "hand",
        "allOf": [{"$ref": GEN_POINTER}],
        "$defs": {"generated": {"type": "object", "required": ["type"]}},
    }
    good = '{"properties": {"from_parent": {"type": "string"}}}'
    broken = '{"title": {{name}}'  # not valid JSON

    schema = store(characteristic(), broken, stored, parent_template=good)

    assert schema == stored


def test_full_generation_applies_every_template(store):
    """The counterpart: with both templates valid, both are applied."""
    good = '{"properties": {"from_parent": {"type": "string"}}}'
    template = '{"title": "{{name}}", "properties": {"own": {"type": "number"}}}'

    schema = store(characteristic(), template, None, parent_template=good)

    generated = schema["$defs"]["generated"]
    assert generated["properties"]["from_parent"] == {"type": "string"}
    assert generated["properties"]["own"] == {"type": "number"}


@pytest.mark.parametrize("definitions", [True, False])
def test_a_non_dict_stored_slot_is_replaced(store, definitions):
    """A malformed jsonschema slot must not abort the upload of the entity."""
    entity = characteristic() if definitions else category()
    template = '{"title": "{{name}}", "type": "object"}'

    schema = store(entity, template, "this slot is not an object")

    assert isinstance(schema, dict)
    assert schema["title"] == entity.name


def test_replace_remote_does_not_merge_into_the_remote_schema(store):
    """'replace remote' removes what is not in the local entity.

    The policy leaves the remote jsonschema slot on the page object, so the
    regeneration merged the new schema into the stale remote one. A page with a
    corrupted schema could then not be repaired by storing it again.
    """
    stored = {"title": "hand", "properties": {"stale": {"type": "string"}}}
    template = '{"title": "{{name}}", "properties": {"gen": {"type": "number"}}}'

    schema = store(
        category(),
        template,
        stored,
        overwrite=AddOverwriteClassOptions.replace_remote,
        offline=False,
    )

    assert "stale" not in schema["properties"]
    assert schema["properties"]["gen"] == {"type": "number"}


def test_root_level_second_save_with_a_changed_template_unions(store):
    """Known deviation, shared with the form editor.

    ROOT_LEVEL mode merges into the stored schema and merge_deep() concatenates
    arrays. Nothing marks which root members the last generation wrote, so an
    entry a later template no longer produces cannot be told from a hand written
    one and stays. The form editor behaves the same way. Pinned here so that a
    change is a deliberate one.
    """
    first_template = '{"title": "{{name}}", "required": ["gen"]}'
    second_template = '{"title": "{{name}}", "required": ["other"]}'

    first = store(category(), first_template, None)
    assert first["required"] == ["gen"]

    second = store(category(), second_template, first)

    assert second["required"] == ["gen", "other"]
