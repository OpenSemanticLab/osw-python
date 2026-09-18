"""Unit tests for osw.service.ops.search (Operation.fn called directly).

Importing ``osw.service.ops.search`` registers its operations in
``osw.service.registry.REGISTRY`` at import time, so this module must not
clear the registry the way ``test_service_registry.py`` does.
"""

from unittest.mock import MagicMock

import pytest

from osw.service import errors
from osw.service.config import Settings
from osw.service.context import Context, Policy
from osw.service.ops import search


def _settings() -> Settings:
    return Settings(domain="wiki.example.org", username="u", password="p")


def test_search_ask_calls_semantic_search():
    osw = MagicMock()
    osw.site.semantic_search.return_value = ["Item:OSW1", "Item:OSW2"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_ask(ctx, ask_query="[[Category:Item]]")

    assert result["titles"] == ["Item:OSW1", "Item:OSW2"]
    assert result["count"] == 2
    osw.site.semantic_search.assert_called_once()


def test_search_titles_calls_prefix_search():
    osw = MagicMock()
    osw.site.prefix_search.return_value = ["Item:OSW1"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_titles(ctx, text="OSW")

    assert result["titles"] == ["Item:OSW1"]
    assert result["count"] == 1
    assert result["truncated"] is False
    osw.site.prefix_search.assert_called_once()


def test_search_content_calls_content_search():
    osw = MagicMock()
    osw.site.content_search.return_value = ["Item:OSW1"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_content(ctx, text="sensor")

    assert result["titles"] == ["Item:OSW1"]
    assert result["count"] == 1
    assert result["truncated"] is False
    osw.site.content_search.assert_called_once()


def test_search_entities_calls_query_instances():
    osw = MagicMock()
    osw.query_instances.return_value = ["Item:OSW1", "Item:OSW2"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_entities(ctx, category="Category:Item")

    assert result["titles"] == ["Item:OSW1", "Item:OSW2"]
    assert result["count"] == 2
    osw.query_instances.assert_called_once()


def test_sparql_query_without_endpoint_raises_not_configured():
    ctx = Context(_settings(), Policy(), osw=MagicMock())

    with pytest.raises(errors.NotConfigured):
        search.sparql_query(ctx, query="SELECT * WHERE {?s ?p ?o}")


def test_search_ask_flags_truncation_at_the_requested_limit():
    osw = MagicMock()
    osw.site.semantic_search.return_value = ["Item:OSW1", "Item:OSW2"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_ask(ctx, ask_query="[[Category:Item]]", limit=2)

    assert result["count"] == 2
    assert result["truncated"] is True


def test_search_ask_flags_truncation_at_a_limit_inside_the_query():
    """The query's own limit reaches the wiki, so it decides truncation."""
    osw = MagicMock()
    osw.site.semantic_search.return_value = ["Item:OSW1", "Item:OSW2"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_ask(ctx, ask_query="[[Category:Item]]|limit=2", limit=100)

    assert result["truncated"] is True


def test_search_ask_below_the_limit_is_not_truncated():
    osw = MagicMock()
    osw.site.semantic_search.return_value = ["Item:OSW1"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_ask(ctx, ask_query="[[Category:Item]]", limit=2)

    assert result["truncated"] is False


def test_search_ask_with_limit_zero_in_the_query_is_not_truncated():
    """'limit=0' asks for no results, so meeting it is not truncation."""
    osw = MagicMock()
    osw.site.semantic_search.return_value = []
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_ask(ctx, ask_query="[[Category:Item]]|limit=0", limit=100)

    assert result["truncated"] is False


def test_search_titles_flags_truncation_at_the_limit():
    osw = MagicMock()
    osw.site.prefix_search.return_value = ["Item:OSW1", "Item:OSW2"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_titles(ctx, text="Item", limit=2)

    assert result["truncated"] is True


def test_search_content_flags_truncation_at_the_limit():
    osw = MagicMock()
    osw.site.content_search.return_value = ["Item:OSW1", "Item:OSW2"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_content(ctx, text="sensor", limit=2)

    assert result["truncated"] is True


def test_search_entities_flags_truncation_at_the_limit():
    osw = MagicMock()
    osw.query_instances.return_value = ["Item:OSW1", "Item:OSW2"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_entities(ctx, category="Category:Item", limit=2)

    assert result["truncated"] is True


# -- search_ask: printouts -----------------------------------------------------
def test_search_ask_without_printouts_is_unchanged():
    osw = MagicMock()
    osw.site.semantic_search.return_value = ["Item:OSW1", "Item:OSW2"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_ask(ctx, ask_query="[[Category:Item]]", printouts=None)

    assert result == {
        "titles": ["Item:OSW1", "Item:OSW2"],
        "count": 2,
        "truncated": False,
    }
    param = osw.site.semantic_search.call_args[0][0]
    assert param.query == ["[[Category:Item]]"]
    assert param.return_json is False


def test_search_ask_with_printouts_uses_alias_form_and_return_json():
    osw = MagicMock()
    osw.site.semantic_search.return_value = [{"query": {"results": {}}}]
    ctx = Context(_settings(), Policy(), osw=osw)

    search.search_ask(
        ctx, ask_query="[[Category:Item]]", printouts=["HasStatus", "HasPriority"]
    )

    param = osw.site.semantic_search.call_args[0][0]
    assert param.query == [
        "[[Category:Item]]|?HasStatus=HasStatus|?HasPriority=HasPriority"
    ]
    assert param.return_json is True


def test_search_ask_with_printouts_builds_rows():
    osw = MagicMock()
    osw.site.semantic_search.return_value = [
        {
            "query": {
                "results": {
                    "Item:OSW1": {
                        "fulltext": "Item:OSW1",
                        "exists": "1",
                        "printouts": {"HasStatus": [{"fulltext": "Item:OSWdone"}]},
                    }
                }
            }
        }
    ]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_ask(
        ctx, ask_query="[[Category:Item]]", printouts=["HasStatus"]
    )

    assert result["titles"] == ["Item:OSW1"]
    assert result["count"] == 1
    assert result["truncated"] is False
    assert result["rows"] == [
        {
            "title": "Item:OSW1",
            "printouts": {"HasStatus": [{"fulltext": "Item:OSWdone"}]},
        }
    ]


def test_search_ask_with_printouts_handles_list_shaped_results():
    """SMW serialises a non-empty result set as a dict, but as a list too
    when there is exactly one hit for some query shapes; both must produce
    rows, not an emptied-out result."""
    osw = MagicMock()
    osw.site.semantic_search.return_value = [
        {
            "query": {
                "results": [
                    {
                        "fulltext": "Item:OSW1",
                        "exists": "1",
                        "printouts": {"HasStatus": [{"fulltext": "Item:OSWdone"}]},
                    }
                ]
            }
        }
    ]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_ask(
        ctx, ask_query="[[Category:Item]]", printouts=["HasStatus"]
    )

    assert result["titles"] == ["Item:OSW1"]
    assert result["count"] == 1
    assert result["rows"] == [
        {
            "title": "Item:OSW1",
            "printouts": {"HasStatus": [{"fulltext": "Item:OSWdone"}]},
        }
    ]


# -- search_by_label -----------------------------------------------------------
def test_search_by_label_builds_query_without_category():
    osw = MagicMock()
    osw.site.semantic_search.return_value = ["Item:OSW1"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_by_label(ctx, label="My Task")

    assert result["titles"] == ["Item:OSW1"]
    param = osw.site.semantic_search.call_args[0][0]
    assert param.query == ["[[Display_title_of::My Task]]"]


def test_search_by_label_builds_query_with_category():
    osw = MagicMock()
    osw.site.semantic_search.return_value = ["Item:OSW1"]
    ctx = Context(_settings(), Policy(), osw=osw)

    search.search_by_label(ctx, label="My Task", category="Item")

    param = osw.site.semantic_search.call_args[0][0]
    assert param.query == ["[[Category:Item]][[Display_title_of::My Task]]"]


def test_search_by_label_accepts_category_already_prefixed():
    osw = MagicMock()
    osw.site.semantic_search.return_value = ["Item:OSW1"]
    ctx = Context(_settings(), Policy(), osw=osw)

    search.search_by_label(ctx, label="My Task", category="Category:Item")

    param = osw.site.semantic_search.call_args[0][0]
    assert param.query == ["[[Category:Item]][[Display_title_of::My Task]]"]


def test_search_by_label_rejects_wiki_markup_in_label():
    ctx = Context(_settings(), Policy(), osw=MagicMock())

    with pytest.raises(errors.ValidationError):
        search.search_by_label(ctx, label="x]]evil")


def test_search_by_label_rejects_wiki_markup_in_category():
    ctx = Context(_settings(), Policy(), osw=MagicMock())

    with pytest.raises(errors.ValidationError):
        search.search_by_label(ctx, label="ok", category="x]]evil")
