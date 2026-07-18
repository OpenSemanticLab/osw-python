"""Unit tests for store_entity() per-entity failure reporting (Fix C).

These run fully offline: WtPage.init and the overwrite policy are stubbed so no
network is required, and WtPage.edit is replaced with a controllable stub that
fails for selected page titles.
"""

import pytest

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
    return OSW.construct(site=object())


def _install_edit(monkeypatch, failing_titles):
    def fake_edit(self, *args, **kwargs):
        if self.title in failing_titles:
            raise RuntimeError(f"edit failed for {self.title}")
        return None

    monkeypatch.setattr(WtPage, "edit", fake_edit)


def test_store_entity_serial_single_failure_raises(offline_osw, monkeypatch):
    item = model.Item(label=[model.Label(text="Solo")])
    title = _title(item)
    _install_edit(monkeypatch, {title})

    with pytest.raises(OSW.StoreEntityPartialError) as exc_info:
        offline_osw.store_entity(OSW.StoreEntityParam(entities=[item], parallel=False))

    err = exc_info.value
    assert title in err.failed
    assert isinstance(err.failed[title], RuntimeError)
    # the dropped page must NOT be reported as stored
    assert title not in err.result.pages
    assert err.stored == []


def test_store_entity_parallel_middle_failure_reports_all(offline_osw, monkeypatch):
    items = [model.Item(label=[model.Label(text=f"Item{i}")]) for i in range(3)]
    titles = [_title(it) for it in items]
    failing = titles[1]
    _install_edit(monkeypatch, {failing})

    with pytest.raises(OSW.StoreEntityPartialError) as exc_info:
        offline_osw.store_entity(OSW.StoreEntityParam(entities=items, parallel=True))

    err = exc_info.value
    # the two good entities are recorded as stored (the first exception did not
    # abandon the remaining tasks) ...
    assert set(err.result.pages.keys()) == {titles[0], titles[2]}
    assert set(err.stored) == {titles[0], titles[2]}
    # ... and the failing one is reported instead of being silently dropped
    assert set(err.failed.keys()) == {failing}
    assert isinstance(err.failed[failing], RuntimeError)


def test_store_entity_all_success_returns_result(offline_osw, monkeypatch):
    items = [model.Item(label=[model.Label(text=f"Ok{i}")]) for i in range(3)]
    titles = [_title(it) for it in items]
    _install_edit(monkeypatch, set())  # nothing fails

    result = offline_osw.store_entity(
        OSW.StoreEntityParam(entities=items, parallel=True)
    )

    assert set(result.pages.keys()) == set(titles)
    assert result.failed == {}


def test_store_entity_serial_all_success_returns_result(offline_osw, monkeypatch):
    items = [model.Item(label=[model.Label(text=f"Ser{i}")]) for i in range(2)]
    titles = [_title(it) for it in items]
    _install_edit(monkeypatch, set())

    result = offline_osw.store_entity(
        OSW.StoreEntityParam(entities=items, parallel=False)
    )

    assert set(result.pages.keys()) == set(titles)
    assert result.failed == {}
