"""Unit tests for load_entity() when a category page has no usable schema.

Regression guard for #202: https://github.com/OpenSemanticLab/osw-python/issues/202
load_entity() read each category's schema in a per-page loop without a guard
around it. A category page with no jsonschema slot, a schema without a
"title" key, or a title that is not a string all raised out of the loop and
ended the whole call, so no further title in a multi-title load was ever
processed.

These run fully offline: the fake site never touches the network.
"""

import json
from types import SimpleNamespace

import osw.model.entity as model
from osw.core import OSW
from osw.utils.wiki import remove_empty

_CATEGORY = "Category:OSWBadCategoryTest0000000000000000000"


class _FakePage:
    """A page that serves a fixed jsondata or jsonschema slot."""

    def __init__(self, title, jsondata=None, schema=None):
        self.title = title
        self._jsondata = jsondata
        self._schema = schema

    def get_slot_content(self, slot):
        if slot == "jsondata":
            return self._jsondata
        if slot == "jsonschema":
            return self._schema
        return None


class _FakeSite:
    """A site that resolves get_page() by title, so a page fetch and a
    category (schema) fetch return different content."""

    def __init__(self, pages_by_title, cache_enabled=False):
        self._pages_by_title = pages_by_title
        self.cache_enabled = cache_enabled

    def get_cache_enabled(self):
        return self.cache_enabled

    def enable_cache(self):
        self.cache_enabled = True

    def disable_cache(self):
        self.cache_enabled = False

    def get_page(self, param):
        pages = [self._pages_by_title[title] for title in param.titles]
        return SimpleNamespace(pages=pages)


def _bad_category_site(title, schema):
    """A site with one page whose only category serves the given schema."""
    jsondata = {"type": [_CATEGORY], "uuid": "00000000-0000-0000-0000-000000000000"}
    entity_page = _FakePage(title, jsondata=jsondata)
    category_page = _FakePage(_CATEGORY, schema=schema)
    return _FakeSite({title: entity_page, _CATEGORY: category_page})


def test_missing_jsonschema_slot_does_not_raise():
    """get_slot_content("jsonschema") returning None must not raise."""
    title = "Item:BadNoSlot"
    site = _bad_category_site(title, schema=None)
    osw_obj = OSW.construct(site=site)

    result = osw_obj.load_entity(title)

    assert result is None


def test_schema_without_title_key_does_not_raise():
    """A schema dict with no "title" key must not raise."""
    title = "Item:BadNoTitle"
    site = _bad_category_site(title, schema={})
    osw_obj = OSW.construct(site=site)

    result = osw_obj.load_entity(title)

    assert result is None


def test_schema_title_not_a_string_does_not_raise():
    """A "title" that is not a string must not raise."""
    title = "Item:BadTitleType"
    site = _bad_category_site(title, schema={"title": 123})
    osw_obj = OSW.construct(site=site)

    result = osw_obj.load_entity(title)

    assert result is None


def _valid_item_page(title):
    """A page whose category and jsondata build a real model.Item entity."""
    item = model.Item(label=[model.Label(text="Test Item")])
    category = item.type[0]
    jsondata = json.loads(item.json(exclude_none=True))
    remove_empty(jsondata)
    entity_page = _FakePage(title, jsondata=jsondata)
    category_page = _FakePage(category, schema={"title": "Item"})
    return entity_page, category_page, item


def test_bad_category_on_first_page_does_not_block_the_second():
    """A multi-title load must not lose every title because one page's
    category is unusable; the rest of the loop must still be processed."""
    bad_title = "Item:BadFirst"
    good_title = "Item:GoodSecond"

    bad_jsondata = {
        "type": [_CATEGORY],
        "uuid": "11111111-1111-1111-1111-111111111111",
    }
    bad_entity_page = _FakePage(bad_title, jsondata=bad_jsondata)
    bad_category_page = _FakePage(_CATEGORY, schema=None)

    good_entity_page, good_category_page, item = _valid_item_page(good_title)

    site = _FakeSite({
        bad_title: bad_entity_page,
        good_title: good_entity_page,
        _CATEGORY: bad_category_page,
        good_category_page.title: good_category_page,
    })
    osw_obj = OSW.construct(site=site)

    result = osw_obj.load_entity([bad_title, good_title])

    assert len(result) == 1
    assert result[0].uuid == item.uuid


def test_bad_category_logs_the_page_title_and_the_category(caplog):
    """The logged error must name both the failing page and the category, so
    the fault can be traced back to the wiki page that needs a fix."""
    title = "Item:BadLogged"
    site = _bad_category_site(title, schema=None)
    osw_obj = OSW.construct(site=site)

    osw_obj.load_entity(title)

    assert any(
        title in record.message and _CATEGORY in record.message
        for record in caplog.records
    )
