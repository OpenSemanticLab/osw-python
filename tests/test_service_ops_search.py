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
