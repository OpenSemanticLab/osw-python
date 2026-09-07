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


def test_search_entities_calls_semantic_search():
    osw = MagicMock()
    osw.site.semantic_search.return_value = ["Item:OSW1", "Item:OSW2"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_entities(ctx, ask_query="[[Category:Item]]")

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


def test_list_instances_of_category_calls_query_instances():
    osw = MagicMock()
    osw.query_instances.return_value = ["Item:OSW1", "Item:OSW2"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.list_instances_of_category(ctx, category="Category:Item")

    assert result["titles"] == ["Item:OSW1", "Item:OSW2"]
    assert result["count"] == 2
    osw.query_instances.assert_called_once()


def test_sparql_query_without_endpoint_raises_not_configured():
    ctx = Context(_settings(), Policy(), osw=MagicMock())

    with pytest.raises(errors.NotConfigured):
        search.sparql_query(ctx, query="SELECT * WHERE {?s ?p ?o}")


def test_search_entities_flags_truncation_at_the_requested_limit():
    osw = MagicMock()
    osw.site.semantic_search.return_value = ["Item:OSW1", "Item:OSW2"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_entities(ctx, ask_query="[[Category:Item]]", limit=2)

    assert result["count"] == 2
    assert result["truncated"] is True


def test_search_entities_flags_truncation_at_a_limit_inside_the_query():
    """The query's own limit reaches the wiki, so it decides truncation."""
    osw = MagicMock()
    osw.site.semantic_search.return_value = ["Item:OSW1", "Item:OSW2"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_entities(
        ctx, ask_query="[[Category:Item]]|limit=2", limit=100
    )

    assert result["truncated"] is True


def test_search_entities_below_the_limit_is_not_truncated():
    osw = MagicMock()
    osw.site.semantic_search.return_value = ["Item:OSW1"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_entities(ctx, ask_query="[[Category:Item]]", limit=2)

    assert result["truncated"] is False


def test_search_entities_with_limit_zero_in_the_query_is_not_truncated():
    """'limit=0' asks for no results, so meeting it is not truncation."""
    osw = MagicMock()
    osw.site.semantic_search.return_value = []
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.search_entities(
        ctx, ask_query="[[Category:Item]]|limit=0", limit=100
    )

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


def test_list_instances_of_category_flags_truncation_at_the_limit():
    osw = MagicMock()
    osw.query_instances.return_value = ["Item:OSW1", "Item:OSW2"]
    ctx = Context(_settings(), Policy(), osw=osw)

    result = search.list_instances_of_category(ctx, category="Category:Item", limit=2)

    assert result["truncated"] is True
