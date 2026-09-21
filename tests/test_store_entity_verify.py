"""Unit tests for the write verification of store_entity().

Regression guard for #175: store_entity() returned normally and listed a page in
created_pages when that page did not exist on the wiki afterwards. An edit that
raises nothing is not proof that the page was created, and page.changed is True
in the failing case as well. store_entity() must now query the edited pages and
report an absent one in result.failed.

These run fully offline: WtPage.init, the overwrite policy and the existence
query are stubbed, so no network is required.
"""

import pytest

import osw.core as core_mod
import osw.model.entity as model
from osw.core import OSW
from osw.utils.wiki import get_namespace, get_title
from osw.wtsite import WtPage


def _title(entity):
    return f"{get_namespace(entity)}:{get_title(entity)}"


class _FakeMwSite:
    """Records the API queries and answers them from a set of missing titles.

    missing_once holds titles that are reported as missing by the first query
    only, which is what a read from a lagging database replica looks like.
    """

    def __init__(
        self, missing_titles=(), normalized=None, missing_once=(), fails=False
    ):
        self.missing_titles = set(missing_titles)
        self.missing_once = set(missing_once)
        self.normalized = normalized or {}
        self.fails = fails
        self.queries = []

    def api(self, action, **kwargs):
        assert action == "query"
        if self.fails:
            raise RuntimeError("the API is not reachable")
        titles = kwargs["titles"].split("|")
        self.queries.append(titles)
        missing_now = self.missing_titles | self.missing_once
        self.missing_once = set()
        pages = {}
        for i, title in enumerate(titles):
            reported = self.normalized.get(title, title)
            if title in missing_now:
                pages[str(-(i + 1))] = {"title": reported, "missing": ""}
            else:
                pages[str(i + 1)] = {"title": reported, "pageid": i + 1}
        query = {"pages": pages}
        if self.normalized:
            query["normalized"] = [
                {"from": k, "to": v} for k, v in self.normalized.items()
            ]
        return {"query": query}


class _FakeSite:
    def __init__(self, mw_site):
        self.mw_site = mw_site


@pytest.fixture
def offline_osw(monkeypatch):
    """An OSW that never touches the network, with a controllable existence query."""
    monkeypatch.setattr(WtPage, "init", lambda self: setattr(self, "exists", False))
    monkeypatch.setattr(
        OSW, "_apply_overwrite_policy", staticmethod(lambda param: param.page)
    )
    monkeypatch.setattr(WtPage, "edit", lambda self, *a, **kw: None)
    # the delay before the confirmation query, not worth waiting for in a test
    monkeypatch.setattr(core_mod, "sleep", lambda *a, **kw: None)

    def _make(missing_titles=(), normalized=None, missing_once=(), fails=False):
        mw_site = _FakeMwSite(missing_titles, normalized, missing_once, fails)
        return OSW.construct(site=_FakeSite(mw_site)), mw_site

    return _make


def test_absent_page_is_reported_as_failed(offline_osw):
    item = model.Item(label=[model.Label(text="Ghost")])
    title = _title(item)
    osw_obj, _mw_site = offline_osw(missing_titles=[title])

    with pytest.raises(OSW.StoreEntityPartialError) as exc_info:
        osw_obj.store_entity(OSW.StoreEntityParam(entities=[item], parallel=False))

    err = exc_info.value
    assert title in err.failed
    assert isinstance(err.failed[title], OSW.PageNotCreatedError)
    assert err.failed[title].title == title
    assert title not in err.result.pages
    assert err.stored == []


def test_present_page_is_reported_as_stored(offline_osw):
    item = model.Item(label=[model.Label(text="Real")])
    title = _title(item)
    osw_obj, mw_site = offline_osw()

    result = osw_obj.store_entity(OSW.StoreEntityParam(entities=[item], parallel=False))

    assert set(result.pages.keys()) == {title}
    assert result.failed == {}
    assert mw_site.queries == [[title]]


def test_only_the_absent_page_of_a_batch_is_reported(offline_osw):
    items = [model.Item(label=[model.Label(text=f"Batch{i}")]) for i in range(3)]
    titles = [_title(it) for it in items]
    osw_obj, _mw_site = offline_osw(missing_titles=[titles[1]])

    with pytest.raises(OSW.StoreEntityPartialError) as exc_info:
        osw_obj.store_entity(OSW.StoreEntityParam(entities=items, parallel=True))

    err = exc_info.value
    assert set(err.result.pages.keys()) == {titles[0], titles[2]}
    assert set(err.failed.keys()) == {titles[1]}


def test_verification_is_skipped_when_disabled(offline_osw):
    item = model.Item(label=[model.Label(text="Unchecked")])
    title = _title(item)
    osw_obj, mw_site = offline_osw(missing_titles=[title])

    result = osw_obj.store_entity(
        OSW.StoreEntityParam(entities=[item], parallel=False, verify_write=False)
    )

    assert mw_site.queries == []
    assert set(result.pages.keys()) == {title}


def test_verification_is_skipped_offline(offline_osw):
    item = model.Item(label=[model.Label(text="Offline")])
    title = _title(item)
    osw_obj, mw_site = offline_osw(missing_titles=[title])

    result = osw_obj.store_entity(
        OSW.StoreEntityParam(entities=[item], parallel=False, offline=True)
    )

    assert mw_site.queries == []
    assert set(result.pages.keys()) == {title}


def test_a_missing_page_is_confirmed_by_a_second_query(offline_osw):
    item = model.Item(label=[model.Label(text="Ghost")])
    title = _title(item)
    osw_obj, mw_site = offline_osw(missing_titles=[title])

    with pytest.raises(OSW.StoreEntityPartialError):
        osw_obj.store_entity(OSW.StoreEntityParam(entities=[item], parallel=False))

    assert mw_site.queries == [[title], [title]]


def test_a_page_that_appears_on_the_second_query_is_not_reported(offline_osw):
    """A read answered by a lagging database replica must not fail the store."""
    items = [model.Item(label=[model.Label(text=f"Lag{i}")]) for i in range(2)]
    titles = [_title(it) for it in items]
    osw_obj, mw_site = offline_osw(missing_once=[titles[0]])

    result = osw_obj.store_entity(OSW.StoreEntityParam(entities=items, parallel=False))

    assert set(result.pages.keys()) == set(titles)
    assert result.failed == {}
    # the second query asks only for the title the first one reported as missing
    assert mw_site.queries[1] == [titles[0]]


def test_a_failing_query_keeps_the_pages_and_does_not_raise(offline_osw):
    items = [model.Item(label=[model.Label(text=f"Unverified{i}")]) for i in range(2)]
    titles = [_title(it) for it in items]
    osw_obj, _mw_site = offline_osw(fails=True)

    result = osw_obj.store_entity(OSW.StoreEntityParam(entities=items, parallel=False))

    assert set(result.pages.keys()) == set(titles)
    assert result.failed == {}


def test_titles_are_queried_in_batches_of_fifty(offline_osw):
    osw_obj, mw_site = offline_osw()
    titles = [f"Item:OSW{i:04d}" for i in range(120)]

    missing = osw_obj._get_missing_page_titles(titles)

    assert missing == []
    assert [len(batch) for batch in mw_site.queries] == [50, 50, 20]


def test_missing_titles_are_mapped_back_to_the_requested_form(offline_osw):
    requested = "Item:OSW_with_underscores"
    osw_obj, _mw_site = offline_osw(
        missing_titles=[requested],
        normalized={requested: "Item:OSW with underscores"},
    )

    assert osw_obj._get_missing_page_titles([requested]) == [requested]
