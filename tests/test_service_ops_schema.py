"""Unit tests for osw.service.ops.schema (Operation.fn called directly).

Importing ``osw.service.ops.schema`` registers its operations in
``osw.service.registry.REGISTRY`` at import time, so this module must not
clear the registry the way ``test_service_registry.py`` does.
"""

from unittest.mock import MagicMock

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
