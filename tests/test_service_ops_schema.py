"""Unit tests for osw.service.ops.schema (Operation.fn called directly).

Importing ``osw.service.ops.schema`` registers its operations in
``osw.service.registry.REGISTRY`` at import time, so this module must not
clear the registry the way ``test_service_registry.py`` does.
"""

import json
from unittest.mock import MagicMock

import pytest

from osw.service import errors
from osw.service.config import Settings
from osw.service.context import Context, Policy
from osw.service.ops import schema


def _settings() -> Settings:
    return Settings(domain="wiki.example.org", username="u", password="p")


def test_get_category_schema_returns_schema_when_page_exists():
    page = MagicMock()
    page.exists = True
    page.get_slot_content.return_value = {"type": "object"}
    osw = MagicMock()
    osw.site.get_page.return_value.pages = [page]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = schema.get_category_schema(ctx, category="Category:Item")

    assert result == {
        "category": "Category:Item",
        "exists": True,
        "schema": {"type": "object"},
        "truncated": False,
    }
    page.get_slot_content.assert_called_with("jsonschema")


def test_get_category_schema_returns_not_exists_for_missing_page():
    page = MagicMock()
    page.exists = False
    osw = MagicMock()
    osw.site.get_page.return_value.pages = [page]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = schema.get_category_schema(ctx, category="Category:Missing")

    assert result == {
        "category": "Category:Missing",
        "exists": False,
        "schema": None,
    }


def test_get_category_schema_resolve_false_is_unchanged():
    page = MagicMock()
    page.exists = True
    page.get_slot_content.return_value = {"type": "object"}
    osw = MagicMock()
    osw.site.get_page.return_value.pages = [page]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = schema.get_category_schema(ctx, category="Category:Item", resolve=False)

    assert result == {
        "category": "Category:Item",
        "exists": True,
        "schema": {"type": "object"},
        "truncated": False,
    }
    assert "skipped" not in result


def _page(slot_content, exists=True):
    page = MagicMock()
    page.exists = exists
    page.get_slot_content.return_value = slot_content
    return page


def _site_with_pages(pages_by_title):
    def get_page(param):
        title = param.titles[0]
        page = pages_by_title.get(title) or _page(None, exists=False)
        result = MagicMock()
        result.pages = [page]
        return result

    site = MagicMock()
    site.get_page.side_effect = get_page
    return site


def test_get_category_schema_resolve_true_merges_two_level_chain():
    pages = {
        "Category:Child": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:Parent"
                "?action=raw&slot=jsonschema"
            ],
            "properties": {"child_field": {"type": "string"}},
            "required": ["child_field"],
        }),
        "Category:Parent": _page({
            "properties": {"parent_field": {"type": "string"}},
            "required": ["parent_field"],
        }),
    }
    osw = MagicMock()
    osw.site = _site_with_pages(pages)
    ctx = Context(_settings(), Policy(), osw=osw)

    result = schema.get_category_schema(ctx, category="Category:Child", resolve=True)

    assert result["resolved"] is True
    assert result["schema"]["properties"]["parent_field"] == {"type": "string"}
    assert result["schema"]["properties"]["child_field"] == {"type": "string"}
    assert result["schema"]["required"] == ["parent_field", "child_field"]
    assert result["sources"] == ["Category:Child", "Category:Parent"]
    assert result["skipped"] == []


def test_get_category_schema_resolve_true_child_property_overrides_parent():
    pages = {
        "Category:Child": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:Parent"
                "?action=raw&slot=jsonschema"
            ],
            "properties": {"shared": {"type": "string", "title": "child"}},
        }),
        "Category:Parent": _page({
            "properties": {"shared": {"type": "string", "title": "parent"}},
        }),
    }
    osw = MagicMock()
    osw.site = _site_with_pages(pages)
    ctx = Context(_settings(), Policy(), osw=osw)

    result = schema.get_category_schema(ctx, category="Category:Child", resolve=True)

    assert result["schema"]["properties"]["shared"]["title"] == "child"


def test_get_category_schema_resolve_true_reads_jsonschema_parent_from_main_slot():
    pages = {
        "Category:Child": _page({
            "@context": [
                "https://wiki.example.org/wiki/JsonSchema:Parent?action=raw&slot=main"
            ],
            "properties": {"child_field": {"type": "string"}},
        }),
        "JsonSchema:Parent": _page({
            "properties": {"parent_field": {"type": "string"}},
        }),
    }
    osw = MagicMock()
    osw.site = _site_with_pages(pages)
    ctx = Context(_settings(), Policy(), osw=osw)

    result = schema.get_category_schema(ctx, category="Category:Child", resolve=True)

    assert "parent_field" in result["schema"]["properties"]
    pages["Category:Child"].get_slot_content.assert_called_with("jsonschema")
    pages["JsonSchema:Parent"].get_slot_content.assert_called_with("main")


def test_get_category_schema_resolve_true_skips_a_missing_parent():
    pages = {
        "Category:Child": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:MissingParent"
                "?action=raw&slot=jsonschema"
            ],
            "properties": {"child_field": {"type": "string"}},
        }),
    }
    osw = MagicMock()
    osw.site = _site_with_pages(pages)
    ctx = Context(_settings(), Policy(), osw=osw)

    result = schema.get_category_schema(ctx, category="Category:Child", resolve=True)

    assert result["schema"]["properties"] == {"child_field": {"type": "string"}}
    assert result["sources"] == ["Category:Child"]
    assert result["skipped"] == [
        {"title": "Category:MissingParent", "reason": "page does not exist"}
    ]


def test_get_category_schema_resolve_true_skips_a_parent_with_unparsable_slot():
    pages = {
        "Category:Child": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:Parent"
                "?action=raw&slot=jsonschema"
            ],
            "properties": {"child_field": {"type": "string"}},
        }),
        "Category:Parent": _page("{not valid json"),
    }
    osw = MagicMock()
    osw.site = _site_with_pages(pages)
    ctx = Context(_settings(), Policy(), osw=osw)

    result = schema.get_category_schema(ctx, category="Category:Child", resolve=True)

    assert result["schema"]["properties"] == {"child_field": {"type": "string"}}
    assert result["sources"] == ["Category:Child"]
    assert len(result["skipped"]) == 1
    assert result["skipped"][0]["title"] == "Category:Parent"
    assert result["skipped"][0]["reason"].startswith("could not be read: ")


def test_get_category_schema_resolve_true_skips_a_parent_with_no_schema_slot():
    pages = {
        "Category:Child": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:Parent"
                "?action=raw&slot=jsonschema"
            ],
            "properties": {"child_field": {"type": "string"}},
        }),
        "Category:Parent": _page(None, exists=True),
    }
    osw = MagicMock()
    osw.site = _site_with_pages(pages)
    ctx = Context(_settings(), Policy(), osw=osw)

    result = schema.get_category_schema(ctx, category="Category:Child", resolve=True)

    assert result["schema"]["properties"] == {"child_field": {"type": "string"}}
    assert result["sources"] == ["Category:Child"]
    assert result["skipped"] == [
        {"title": "Category:Parent", "reason": "no schema slot"}
    ]


def test_get_category_schema_resolve_true_diamond_parent_is_not_skipped():
    """Category:Child reaches Category:GrandParent through both
    Category:ParentA and Category:ParentB, a normal diamond in the OSL
    category graph (e.g. Category:OSW44deaa5b806d41a2a88594f562b110e9 /
    Person resolves through 7 pages with a branch); the second arrival must
    not be recorded in ``skipped``."""
    pages = {
        "Category:Child": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:ParentA"
                "?action=raw&slot=jsonschema",
                "https://wiki.example.org/wiki/Category:ParentB"
                "?action=raw&slot=jsonschema",
            ],
            "properties": {"child_field": {"type": "string"}},
        }),
        "Category:ParentA": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:GrandParent"
                "?action=raw&slot=jsonschema"
            ],
            "properties": {"parent_a_field": {"type": "string"}},
        }),
        "Category:ParentB": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:GrandParent"
                "?action=raw&slot=jsonschema"
            ],
            "properties": {"parent_b_field": {"type": "string"}},
        }),
        "Category:GrandParent": _page({
            "properties": {"grand_field": {"type": "string"}},
        }),
    }
    osw = MagicMock()
    osw.site = _site_with_pages(pages)
    ctx = Context(_settings(), Policy(), osw=osw)

    result = schema.get_category_schema(ctx, category="Category:Child", resolve=True)

    assert result["schema"]["properties"] == {
        "child_field": {"type": "string"},
        "parent_a_field": {"type": "string"},
        "parent_b_field": {"type": "string"},
        "grand_field": {"type": "string"},
    }
    assert result["skipped"] == []
    assert result["sources"] == [
        "Category:Child",
        "Category:ParentA",
        "Category:GrandParent",
        "Category:ParentB",
    ]


def test_get_category_schema_resolve_true_terminates_on_a_cycle():
    pages = {
        "Category:A": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:B?action=raw&slot=jsonschema"
            ],
            "properties": {"a_field": {"type": "string"}},
        }),
        "Category:B": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:A?action=raw&slot=jsonschema"
            ],
            "properties": {"b_field": {"type": "string"}},
        }),
    }
    osw = MagicMock()
    osw.site = _site_with_pages(pages)
    ctx = Context(_settings(), Policy(), osw=osw)

    result = schema.get_category_schema(ctx, category="Category:A", resolve=True)

    assert result["schema"]["properties"] == {
        "a_field": {"type": "string"},
        "b_field": {"type": "string"},
    }
    assert result["sources"] == ["Category:A", "Category:B"]


def test_get_category_schema_resolve_true_follows_allof_ref_as_only_parent_link():
    """The parent is reachable only through allOf's $ref, with no @context
    entry pointing at it, so this exercises the allOf branch on its own."""
    pages = {
        "Category:Child": _page({
            "allOf": [
                {
                    "$ref": (
                        "https://wiki.example.org/wiki/Category:Parent"
                        "?action=raw&slot=jsonschema"
                    )
                }
            ],
            "properties": {"child_field": {"type": "string"}},
        }),
        "Category:Parent": _page({
            "properties": {"parent_field": {"type": "string"}},
        }),
    }
    osw = MagicMock()
    osw.site = _site_with_pages(pages)
    ctx = Context(_settings(), Policy(), osw=osw)

    result = schema.get_category_schema(ctx, category="Category:Child", resolve=True)

    assert result["schema"]["properties"] == {
        "child_field": {"type": "string"},
        "parent_field": {"type": "string"},
    }
    assert result["sources"] == ["Category:Child", "Category:Parent"]


def test_get_category_schema_resolve_true_parses_a_string_slot():
    """A real wiki returns slot content as a JSON string, not a dict."""
    pages = {
        "Category:Child": _page(
            json.dumps({
                "properties": {"child_field": {"type": "string"}},
            })
        ),
    }
    osw = MagicMock()
    osw.site = _site_with_pages(pages)
    ctx = Context(_settings(), Policy(), osw=osw)

    result = schema.get_category_schema(ctx, category="Category:Child", resolve=True)

    assert result["schema"]["properties"] == {"child_field": {"type": "string"}}
    assert result["sources"] == ["Category:Child"]


def test_resolve_schema_stops_at_max_depth():
    pages = {
        "Category:L1": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:L2?action=raw&slot=jsonschema"
            ],
            "properties": {"l1_field": {"type": "string"}},
        }),
        "Category:L2": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:L3?action=raw&slot=jsonschema"
            ],
            "properties": {"l2_field": {"type": "string"}},
        }),
        "Category:L3": _page({
            "properties": {"l3_field": {"type": "string"}},
        }),
    }
    osw = MagicMock()
    osw.site = _site_with_pages(pages)
    ctx = Context(_settings(), Policy(), osw=osw)

    merged, sources, skipped = schema._resolve_schema(ctx, "Category:L1", max_depth=2)

    assert sources == ["Category:L1", "Category:L2"]
    assert "l3_field" not in merged["properties"]
    assert merged["properties"] == {
        "l1_field": {"type": "string"},
        "l2_field": {"type": "string"},
    }
    assert skipped == [{"title": "Category:L3", "reason": "maximum depth reached"}]


def test_resolve_schema_page_exhausted_on_one_branch_is_not_skipped_if_read_on_another():
    """Category:SharedX is out of depth budget on the Category:LongBranchL1
    branch but still has budget on the shorter Category:ShortBranch branch,
    so it ends up successfully read; it must appear in ``sources`` and not
    in ``skipped``, even though the walk recorded a depth-exhausted skip for
    it along the way."""
    pages = {
        "Category:Root": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:LongBranchL1"
                "?action=raw&slot=jsonschema",
                "https://wiki.example.org/wiki/Category:ShortBranch"
                "?action=raw&slot=jsonschema",
            ],
            "properties": {"root_field": {"type": "string"}},
        }),
        "Category:LongBranchL1": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:LongBranchL2"
                "?action=raw&slot=jsonschema"
            ],
            "properties": {"long1_field": {"type": "string"}},
        }),
        "Category:LongBranchL2": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:SharedX"
                "?action=raw&slot=jsonschema"
            ],
            "properties": {"long2_field": {"type": "string"}},
        }),
        "Category:ShortBranch": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:SharedX"
                "?action=raw&slot=jsonschema"
            ],
            "properties": {"short_field": {"type": "string"}},
        }),
        "Category:SharedX": _page({
            "properties": {"shared_field": {"type": "string"}},
        }),
    }
    osw = MagicMock()
    osw.site = _site_with_pages(pages)
    ctx = Context(_settings(), Policy(), osw=osw)

    merged, sources, skipped = schema._resolve_schema(ctx, "Category:Root", max_depth=3)

    assert "Category:SharedX" in sources
    assert skipped == []
    assert merged["properties"]["shared_field"] == {"type": "string"}


def test_resolve_schema_page_exhausted_on_two_branches_is_skipped_once():
    """Category:Y is unreachable on either of Category:Root's two branches;
    the walk records a depth-exhausted skip for it once per branch, but the
    reconciled ``skipped`` must hold exactly one entry."""
    pages = {
        "Category:Root": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:BranchA"
                "?action=raw&slot=jsonschema",
                "https://wiki.example.org/wiki/Category:BranchB"
                "?action=raw&slot=jsonschema",
            ],
            "properties": {"root_field": {"type": "string"}},
        }),
        "Category:BranchA": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:Y?action=raw&slot=jsonschema"
            ],
            "properties": {"branch_a_field": {"type": "string"}},
        }),
        "Category:BranchB": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:Y?action=raw&slot=jsonschema"
            ],
            "properties": {"branch_b_field": {"type": "string"}},
        }),
        "Category:Y": _page({
            "properties": {"y_field": {"type": "string"}},
        }),
    }
    osw = MagicMock()
    osw.site = _site_with_pages(pages)
    ctx = Context(_settings(), Policy(), osw=osw)

    _merged, sources, skipped = schema._resolve_schema(
        ctx, "Category:Root", max_depth=2
    )

    assert "Category:Y" not in sources
    assert skipped == [{"title": "Category:Y", "reason": "maximum depth reached"}]


def test_get_category_schema_resolve_true_treats_blank_slot_as_no_schema_slot():
    pages = {
        "Category:Child": _page({
            "@context": [
                "https://wiki.example.org/wiki/Category:Parent"
                "?action=raw&slot=jsonschema"
            ],
            "properties": {"child_field": {"type": "string"}},
        }),
        "Category:Parent": _page("   "),
    }
    osw = MagicMock()
    osw.site = _site_with_pages(pages)
    ctx = Context(_settings(), Policy(), osw=osw)

    result = schema.get_category_schema(ctx, category="Category:Child", resolve=True)

    assert result["schema"]["properties"] == {"child_field": {"type": "string"}}
    assert result["sources"] == ["Category:Child"]
    assert result["skipped"] == [
        {"title": "Category:Parent", "reason": "no schema slot"}
    ]


def test_get_category_property_map_returns_the_smw_property_map():
    osw = MagicMock()
    osw.site.get_smw_property_map.return_value = {"status": "HasStatus"}
    ctx = Context(_settings(), Policy(), osw=osw)

    result = schema.get_category_property_map(ctx, category="Category:Task")

    assert result == {
        "category": "Category:Task",
        "properties": {"status": "HasStatus"},
        "count": 1,
    }
    osw.site.get_smw_property_map.assert_called_once_with("Category:Task")


def test_get_category_property_map_raises_schema_error_when_empty():
    osw = MagicMock()
    osw.site.get_smw_property_map.return_value = {}
    ctx = Context(_settings(), Policy(), osw=osw)

    with pytest.raises(errors.SchemaError):
        schema.get_category_property_map(ctx, category="Category:Missing")


# -- get_field_usage ---------------------------------------------------------
def _usage_ctx(properties, instance_pages, *, more=False, titles=None):
    """A context whose ``Category:Task`` page declares ``properties`` and whose
    ask query returns one row per title.

    ``instance_pages`` maps an instance title to the page object backing it
    (built with ``_page``). ``titles`` overrides the titles the ask query
    returns, so a row can name a page that does not exist. ``more`` adds the
    ``query-continue-offset`` key SMW sets on a cut result set.
    """
    pages = {"Category:Task": _page({"properties": properties})}
    pages.update(instance_pages)
    site = _site_with_pages(pages)
    ask_titles = list(instance_pages) if titles is None else titles
    response = {"query": {"results": {t: {"fulltext": t} for t in ask_titles}}}
    if more:
        response["query-continue-offset"] = 20
    site.semantic_search.return_value = [response]
    osw = MagicMock()
    osw.site = site
    return Context(_settings(), Policy(), osw=osw)


def _populated(result, field):
    return next(e["populated"] for e in result["fields"] if e["field"] == field)


def test_get_field_usage_counts_a_field_populated_in_some_instances():
    ctx = _usage_ctx(
        {"related_to": {"type": "array"}, "label": {"type": "array"}},
        {
            "Item:A": _page({"related_to": ["Item:P"], "label": [{"text": "a"}]}),
            "Item:B": _page({"related_to": [], "label": [{"text": "b"}]}),
            "Item:C": _page({"label": [{"text": "c"}]}),
        },
    )

    result = schema.get_field_usage(ctx, category="Category:Task")

    assert result["category"] == "Category:Task"
    assert result["sampled"] == 3
    assert _populated(result, "related_to") == 1
    assert _populated(result, "label") == 3
    assert result["unreadable"] == []


def test_get_field_usage_treats_empty_values_as_unpopulated_but_false_and_zero_as_used():
    ctx = _usage_ctx(
        {
            "none_field": {},
            "text_field": {},
            "list_field": {},
            "dict_field": {},
            "flag_field": {},
            "count_field": {},
        },
        {
            "Item:A": _page({
                "none_field": None,
                "text_field": "",
                "list_field": [],
                "dict_field": {},
                "flag_field": False,
                "count_field": 0,
            })
        },
    )

    result = schema.get_field_usage(ctx, category="Category:Task")

    assert result["sampled"] == 1
    assert _populated(result, "none_field") == 0
    assert _populated(result, "text_field") == 0
    assert _populated(result, "list_field") == 0
    assert _populated(result, "dict_field") == 0
    assert _populated(result, "flag_field") == 1
    assert _populated(result, "count_field") == 1


def test_get_field_usage_reports_a_declared_field_no_instance_populates():
    ctx = _usage_ctx(
        {"related_to": {}, "projects": {}},
        {"Item:A": _page({"related_to": ["Item:P"]})},
    )

    result = schema.get_field_usage(ctx, category="Category:Task")

    assert result["declared_unused"] == ["projects"]
    assert {"field": "projects", "populated": 0, "declared": True} in result["fields"]


def test_get_field_usage_reports_an_undeclared_field_found_in_an_instance():
    ctx = _usage_ctx(
        {"related_to": {}},
        {"Item:A": _page({"related_to": ["Item:P"], "legacy_field": "x"})},
    )

    result = schema.get_field_usage(ctx, category="Category:Task")

    assert result["undeclared_present"] == ["legacy_field"]
    assert {
        "field": "legacy_field",
        "populated": 1,
        "declared": False,
    } in result["fields"]
    assert result["declared_unused"] == []


def test_get_field_usage_reports_more_instances_when_smw_cut_the_result_set():
    ctx = _usage_ctx(
        {"related_to": {}},
        {"Item:A": _page({"related_to": ["Item:P"]})},
        more=True,
    )

    result = schema.get_field_usage(ctx, category="Category:Task", sample=1)

    assert result["more_instances_exist"] is True


def test_get_field_usage_reports_no_more_instances_without_a_continue_offset():
    ctx = _usage_ctx(
        {"related_to": {}},
        {"Item:A": _page({"related_to": ["Item:P"]})},
    )

    result = schema.get_field_usage(ctx, category="Category:Task")

    assert result["more_instances_exist"] is False


@pytest.mark.parametrize("sample", [0, 101])
def test_get_field_usage_rejects_a_sample_outside_the_allowed_range(sample):
    ctx = Context(_settings(), Policy(), osw=MagicMock())

    with pytest.raises(errors.ValidationError) as excinfo:
        schema.get_field_usage(ctx, category="Category:Task", sample=sample)

    message = str(excinfo.value)
    assert f"'{sample}'" in message
    assert "between 1 and 100" in message


def test_get_field_usage_raises_schema_error_when_the_schema_declares_no_properties():
    ctx = _usage_ctx({}, {})

    with pytest.raises(errors.SchemaError):
        schema.get_field_usage(ctx, category="Category:Task")


def test_get_field_usage_records_unreadable_instances_and_excludes_them():
    ctx = _usage_ctx(
        {"related_to": {}},
        {
            "Item:A": _page({"related_to": ["Item:P"]}),
            "Item:NoSlot": _page(None, exists=True),
        },
        titles=["Item:A", "Item:NoSlot", "Item:Missing"],
    )

    result = schema.get_field_usage(ctx, category="Category:Task")

    assert result["unreadable"] == [
        {"title": "Item:Missing", "reason": "page does not exist"},
        {"title": "Item:NoSlot", "reason": "no jsondata slot"},
    ]
    assert result["sampled"] == 1
    assert _populated(result, "related_to") == 1


def test_get_field_usage_says_why_an_instance_was_unreadable():
    """A connection failure and a deleted page both lower ``sampled``.

    Only the reason separates them, so it has to survive into the result.
    """
    ctx = _usage_ctx(
        {"related_to": {}},
        {
            "Item:A": _page({"related_to": ["Item:P"]}),
            "Item:NotJson": _page("a plain string, not an object"),
        },
        titles=["Item:A", "Item:NotJson", "Item:Boom"],
    )
    broken = ctx.osw.site.get_page

    def fail_on_boom(param):
        if param.titles == ["Item:Boom"]:
            raise ConnectionError("connection reset")
        return broken(param)

    ctx.osw.site.get_page = fail_on_boom

    result = schema.get_field_usage(ctx, category="Category:Task")

    reasons = {e["title"]: e["reason"] for e in result["unreadable"]}
    assert reasons["Item:NotJson"] == "jsondata slot is not a JSON object"
    assert "connection reset" in reasons["Item:Boom"]
    assert result["sampled"] == 1


def test_get_field_usage_orders_fields_by_count_then_name():
    ctx = _usage_ctx(
        {"aaa": {}, "bbb": {}, "ccc": {}, "ddd": {}},
        {
            "Item:A": _page({"bbb": "x", "ccc": "x", "ddd": "x"}),
            "Item:B": _page({"ccc": "x", "ddd": "x"}),
        },
    )

    result = schema.get_field_usage(ctx, category="Category:Task")

    assert [e["field"] for e in result["fields"]] == ["ccc", "ddd", "bbb", "aaa"]


def test_get_field_usage_asks_the_same_query_as_list_instances_of_category():
    """The two operations must agree on what an instance of a category is.

    ``list_instances_of_category`` goes through ``OSW.query_instances``,
    which builds ``[[HasType::Category:<id>]]``. Nothing else would report
    usage for the pages a caller just listed.
    """
    ctx = _usage_ctx({"label": {}}, {"Item:A": _page({"label": ["x"]})})

    schema.get_field_usage(ctx, category="Category:Task", sample=7)

    param = ctx.osw.site.semantic_search.call_args[0][0]
    # SearchParam normalises a single query string to a one-element list.
    assert param.query == ["[[HasType::Category:Task]]"]
    assert param.limit == 7
    assert param.return_json is True


def test_get_field_usage_reads_no_more_pages_than_sample():
    """A wiki that ignores the limit must not multiply the page reads."""
    pages = {f"Item:{i}": _page({"label": ["x"]}) for i in range(5)}
    ctx = _usage_ctx({"label": {}}, pages)

    result = schema.get_field_usage(ctx, category="Category:Task", sample=2)

    assert result["sampled"] == 2


def test_get_field_usage_keeps_rows_from_a_non_empty_results_array():
    """SMW can serialise results as an array rather than an object.

    Dropping that form would report a populated category as having no
    instances at all.
    """
    ctx = _usage_ctx({"label": {}}, {"Item:A": _page({"label": ["x"]})})
    ctx.osw.site.semantic_search.return_value = [
        {"query": {"results": [{"fulltext": "Item:A"}]}}
    ]

    result = schema.get_field_usage(ctx, category="Category:Task")

    assert result["sampled"] == 1
    assert _populated(result, "label") == 1


@pytest.mark.parametrize("bad", ["Category:A]]", "[[Category:A", "Category:A|x"])
def test_get_field_usage_rejects_a_category_that_could_alter_the_ask_query(bad):
    """Same guard the search and task operations apply to a category name.

    Without it the counts would describe a different set of pages than the
    caller asked about.
    """
    ctx = _usage_ctx({"label": {}}, {})

    with pytest.raises(errors.ValidationError):
        schema.get_field_usage(ctx, category=bad)

    ctx.osw.site.semantic_search.assert_not_called()


def test_get_field_usage_reads_instances_uncached():
    """A write earlier in the same process can leave the page cache enabled.

    The cached path would then count a revision from before that write, so
    the instance reads disable the cache exactly as the schema walk does.
    """
    ctx = _usage_ctx({"label": {}}, {"Item:A": _page({"label": [{"text": "a"}]})})
    ctx.osw.site.get_cache_enabled.return_value = True

    result = schema.get_field_usage(ctx, category="Category:Task")

    assert result["sampled"] == 1
    assert ctx.osw.site.disable_cache.called


def test_get_field_usage_reports_no_unused_fields_when_nothing_was_sampled():
    """A category whose instances all declare a subcategory matches no row.

    Reporting every declared field as unused would then state a conclusion
    drawn from zero observations, so ``declared_unused`` stays empty and
    ``fields`` alone carries the zero counts.
    """
    ctx = _usage_ctx({"related_to": {}, "label": {}}, {}, titles=[])

    result = schema.get_field_usage(ctx, category="Category:Task")

    assert result["sampled"] == 0
    assert result["declared_unused"] == []
    assert result["undeclared_present"] == []
    # Every count would be 0 here, which reads as 'no field is in use'.
    assert result["fields"] == []
