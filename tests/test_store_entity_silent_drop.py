"""Unit tests for store_entity() dropping entities without recording a failure.

Regression guard for #183: https://github.com/OpenSemanticLab/osw-python/issues/183
store_entity_() returned plainly (instead of raising) when it could not determine
an entity's title or namespace. A plain return is not an exception, so the
collector loop in store_entity() never recorded the entity in failed, and it was
never in created_pages either: the entity was silently dropped without being
reported to the caller. store_entity_() must now raise in both cases so the
existing collector loop records them.

These run fully offline: WtPage.init, the overwrite policy, WtPage.edit and the
write verification are stubbed, so no network is required.
"""

import pytest

import osw.core as core_mod
import osw.model.entity as model
from osw.core import OSW
from osw.utils.wiki import get_namespace, get_title
from osw.wtsite import WtPage


def _title(entity):
    return f"{get_namespace(entity)}:{get_title(entity)}"


@pytest.fixture
def offline_osw(monkeypatch):
    # no network when a WtPage is constructed with do_init=True; mimic the
    # do_init=False branch of WtPage.__init__ which sets .exists
    monkeypatch.setattr(WtPage, "init", lambda self: setattr(self, "exists", False))
    # bypass the overwrite policy: return the page that was built for the entity
    monkeypatch.setattr(
        OSW, "_apply_overwrite_policy", staticmethod(lambda param: param.page)
    )
    monkeypatch.setattr(WtPage, "edit", lambda self, *a, **kw: None)
    # the write verification would query the wiki. These tests are not about
    # verification, so report every edited page as existing. See
    # tests/test_store_entity_verify.py for the write verification tests.
    monkeypatch.setattr(OSW, "_get_missing_page_titles", lambda self, titles: [])
    return OSW.construct(site=object())


def test_title_failure_is_reported_serial(offline_osw, monkeypatch):
    def _raise_get_title(entity):
        raise RuntimeError("boom")

    monkeypatch.setattr(core_mod, "get_title", _raise_get_title)
    item = model.Item(label=[model.Label(text="Solo")])

    with pytest.raises(OSW.StoreEntityPartialError) as exc_info:
        offline_osw.store_entity(OSW.StoreEntityParam(entities=[item], parallel=False))

    err = exc_info.value
    assert len(err.failed) == 1
    (exc,) = err.failed.values()
    assert isinstance(exc, ValueError)
    assert "Error getting title for entity" in str(exc)


def test_title_failure_is_reported_parallel(offline_osw, monkeypatch):
    def _raise_get_title(entity):
        raise RuntimeError("boom")

    monkeypatch.setattr(core_mod, "get_title", _raise_get_title)
    item = model.Item(label=[model.Label(text="Solo")])

    with pytest.raises(OSW.StoreEntityPartialError) as exc_info:
        offline_osw.store_entity(OSW.StoreEntityParam(entities=[item], parallel=True))

    err = exc_info.value
    assert len(err.failed) == 1
    (exc,) = err.failed.values()
    assert isinstance(exc, ValueError)
    assert "Error getting title for entity" in str(exc)


def test_missing_namespace_is_reported(offline_osw, monkeypatch):
    monkeypatch.setattr(core_mod, "get_namespace", lambda entity: None)
    item = model.Item(label=[model.Label(text="NoNamespace")])

    with pytest.raises(OSW.StoreEntityPartialError) as exc_info:
        offline_osw.store_entity(OSW.StoreEntityParam(entities=[item], parallel=False))

    err = exc_info.value
    assert len(err.failed) == 1
    (exc,) = err.failed.values()
    assert isinstance(exc, TypeError)
    assert "Unsupported entity type" in str(exc)


def test_missing_title_is_reported(offline_osw, monkeypatch):
    monkeypatch.setattr(core_mod, "get_title", lambda entity: None)
    item = model.Item(label=[model.Label(text="NoTitle")])

    with pytest.raises(OSW.StoreEntityPartialError) as exc_info:
        offline_osw.store_entity(OSW.StoreEntityParam(entities=[item], parallel=False))

    err = exc_info.value
    assert len(err.failed) == 1
    (exc,) = err.failed.values()
    assert isinstance(exc, TypeError)
    assert "Unsupported entity type" in str(exc)


def test_only_the_failing_entity_of_a_batch_is_reported(offline_osw, monkeypatch):
    real_get_title = get_title
    good_item = model.Item(label=[model.Label(text="Good")])
    bad_item = model.Item(label=[model.Label(text="Bad")])
    good_title = _title(good_item)

    # store_entity() re-validates its 'entities' param, so the object identity
    # of good_item/bad_item is not preserved past that point. Recognize the
    # failing entity by its label instead.
    def _get_title(entity):
        if entity.label and entity.label[0].text == "Bad":
            raise RuntimeError("boom")
        return real_get_title(entity)

    monkeypatch.setattr(core_mod, "get_title", _get_title)

    with pytest.raises(OSW.StoreEntityPartialError) as exc_info:
        offline_osw.store_entity(
            OSW.StoreEntityParam(entities=[good_item, bad_item], parallel=False)
        )

    err = exc_info.value
    assert len(err.result.pages) == 1
    assert len(err.failed) == 1
    assert good_title in err.result.pages
    assert err.stored == [good_title]


def test_normal_path_is_unaffected(offline_osw):
    item = model.Item(label=[model.Label(text="Fine")])
    title = _title(item)

    result = offline_osw.store_entity(
        OSW.StoreEntityParam(entities=[item], parallel=False)
    )

    assert set(result.pages.keys()) == {title}
    assert result.failed == {}
