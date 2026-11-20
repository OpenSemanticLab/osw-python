"""Unit tests for the page title of Property entities.

A Property entity is stored as 'Property:<name>' (get_title from the opensemantic
package). Writing a property whose name changed would create a second property
page with the same uuid, so store_entity_() refuses it when the wiki holds the
uuid under a different 'Property:' title.

These run fully offline: WtPage.init, the overwrite policy, WtPage.edit and the
write verification are stubbed and the site is a MagicMock.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from opensemantic.core.v1 import AnnotationProperty, Label

import osw.model.entity as model
from osw.core import OSW
from osw.service import errors
from osw.service.config import Settings
from osw.service.context import Context, Policy
from osw.service.ops import entities
from osw.wtsite import WtPage


@pytest.fixture
def edits(monkeypatch):
    """The titles of the pages an edit was sent for."""
    sent = []
    monkeypatch.setattr(WtPage, "init", lambda self: setattr(self, "exists", False))
    monkeypatch.setattr(
        OSW, "_apply_overwrite_policy", staticmethod(lambda param: param.page)
    )
    monkeypatch.setattr(WtPage, "edit", lambda self, *a, **kw: sent.append(self.title))
    monkeypatch.setattr(OSW, "_get_missing_page_titles", lambda self, titles: [])
    return sent


def _osw(hits=()):
    site = MagicMock()
    site.semantic_search.return_value = list(hits)
    return OSW.construct(site=site)


def _prop(name, **kwargs):
    return AnnotationProperty(name=name, label=[Label(text=name)], **kwargs)


def _store(osw, entity):
    return osw.store_entity(OSW.StoreEntityParam(entities=[entity], parallel=False))


def test_property_without_meta_is_written_to_its_name(edits):
    osw = _osw()
    _store(osw, _prop("HasName"))
    assert edits == ["Property:HasName"]


def test_update_with_same_name_passes(edits):
    prop = _prop("HasName")
    osw = _osw(hits=["Property:HasName"])
    _store(osw, prop)
    assert edits == ["Property:HasName"]
    osw.site.semantic_search.assert_called_once_with(f"[[HasUuid::{prop.uuid}]]")


def test_no_hit_passes(edits):
    osw = _osw(hits=[])
    _store(osw, _prop("HasName"))
    assert edits == ["Property:HasName"]


def test_renamed_property_is_refused(edits):
    prop = _prop("NewName")
    osw = _osw(hits=["Property:OldName"])
    with pytest.raises(OSW.StoreEntityPartialError) as exc_info:
        _store(osw, prop)
    (exc,) = exc_info.value.failed.values()
    assert isinstance(exc, ValueError)
    text = str(exc)
    assert "Property:OldName" in text
    assert "Property:NewName" in text
    assert str(prop.uuid) in text
    assert "move" in text
    assert edits == []


def test_hit_in_another_namespace_is_ignored(edits):
    osw = _osw(hits=["Item:OSW123"])
    _store(osw, _prop("HasName"))
    assert edits == ["Property:HasName"]


@pytest.mark.parametrize(
    "name, hit",
    [("hasName", "Property:HasName"), ("Has_Name", "Property:Has Name")],
)
def test_title_comparison_is_normalized_like_mediawiki(edits, name, hit):
    osw = _osw(hits=[hit])
    _store(osw, _prop(name))
    assert len(edits) == 1


def test_explicit_meta_title_wins_over_name(edits):
    prop = _prop("NewName")
    prop.meta = _meta(title="Pinned")
    osw = _osw(hits=["Property:Pinned"])
    _store(osw, prop)
    assert edits == ["Property:Pinned"]


def test_item_keeps_the_uuid_title_and_runs_no_query(edits):
    item = model.Item(label=[model.Label(text="Solo")])
    osw = _osw()
    _store(osw, item)
    assert edits == [f"Item:OSW{str(item.uuid).replace('-', '')}"]
    osw.site.semantic_search.assert_not_called()


def _meta(title=None, namespace=None):
    return model.Meta(wiki_page=model.WikiPage(title=title, namespace=namespace))


# -- delete_entity -----------------------------------------------------------
def _delete(entity):
    site = MagicMock()
    page = MagicMock(exists=True)
    site.get_page.return_value.pages = [page]
    OSW.construct(site=site).delete_entity(
        OSW.DeleteEntityParam(entities=[entity], parallel=False)
    )
    (call,) = site.get_page.call_args_list
    page.delete.assert_called_once()
    return call.args[0].titles


def test_delete_property_without_meta_targets_its_name():
    assert _delete(_prop("HasName")) == ["Property:HasName"]


def test_delete_property_with_meta_title_targets_the_meta_title():
    prop = _prop("HasName")
    prop.meta = _meta(title="Pinned")
    assert _delete(prop) == ["Property:Pinned"]


# -- service op --------------------------------------------------------------
def test_create_or_update_entity_surfaces_the_rename_refusal(monkeypatch, edits):
    osw = _osw(hits=["Property:OldName"])
    monkeypatch.setattr(
        OSW, "fetch_schema", lambda self, param: MagicMock(error_messages=[])
    )
    monkeypatch.setattr(
        entities, "_resolve_category_class", lambda category: AnnotationProperty
    )
    monkeypatch.setattr(entities.config, "get_active_domain", lambda: "w.example.org")
    ctx = Context(
        Settings(domain="w.example.org", username="u", password="p"),
        Policy(),
        osw=osw,
    )
    with pytest.raises(errors.OpError) as exc_info:
        entities.create_or_update_entity(
            ctx,
            category="Category:OSW0000000000000000000000000000AnnotationProperty",
            jsondata={
                "uuid": str(uuid4()),
                "name": "NewName",
                "label": [{"text": "x"}],
            },
        )
    text = str(exc_info.value)
    assert "Property:OldName" in text
    assert "Property:NewName" in text
    assert "move" in text
    assert edits == []
    # the MCP wire type stays the one a failed store had before
    assert exc_info.value.payload()["type"] == "StoreEntityPartialError"
