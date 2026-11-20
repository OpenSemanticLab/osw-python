"""Unit tests for the page cache handling of OSW.fetch_schema().

Regression guard for #176: the cache state was taken and restored once per
schema title inside _fetch_schema(). With two or more titles the second
snapshot already read the state the first call had set, so the restore never
disabled the cache again. An early return or an exception skipped the restore
as well. fetch_schema() must now take the state once and restore it in every
case.
"""

import threading

import pytest

from osw.core import OSW
from osw.wtsite import WtSite


def _make_fake_wtsite(cache_enabled: bool) -> WtSite:
    """A WtSite that performs no network calls, with a known cache state."""
    ws = WtSite.__new__(WtSite)
    ws._session_lock = threading.RLock()
    ws._page_cache = {}
    ws._cache_enabled = cache_enabled
    return ws


def _make_osw(cache_enabled: bool) -> OSW:
    """An OSW bound to that WtSite, bypassing __init__ and validation."""
    return OSW.construct(site=_make_fake_wtsite(cache_enabled))


def _stub_fetch_schema(
    monkeypatch, seen_states: list, fail_on: str = None, leaks: bool = False
):
    """Replace the per-title worker. Records the cache state it is called with.

    With leaks=True the worker enables the cache and never restores it, which is
    what the previous _fetch_schema() did for every title but the last one.
    """

    def stub(self, fetchSchemaParam=None):
        seen_states.append(self.site.get_cache_enabled())
        if leaks:
            self.site.enable_cache()
        if fail_on is not None and fetchSchemaParam.schema_title == fail_on:
            raise RuntimeError("fetching the schema failed")
        return OSW.FetchSchemaResult(
            fetched_schema_titles=[fetchSchemaParam.schema_title]
        )

    monkeypatch.setattr(OSW, "_fetch_schema", stub)


def test_cache_is_disabled_again_after_several_titles(monkeypatch):
    osw_obj = _make_osw(cache_enabled=False)
    seen_states = []
    _stub_fetch_schema(monkeypatch, seen_states)

    osw_obj.fetch_schema(
        OSW.FetchSchemaParam(schema_title=["Category:Item", "Category:Entity"])
    )

    assert seen_states == [True, True]
    assert osw_obj.site.get_cache_enabled() is False


def test_cache_is_disabled_again_after_a_single_title(monkeypatch):
    osw_obj = _make_osw(cache_enabled=False)
    seen_states = []
    _stub_fetch_schema(monkeypatch, seen_states)

    osw_obj.fetch_schema(OSW.FetchSchemaParam(schema_title="Category:Item"))

    assert seen_states == [True]
    assert osw_obj.site.get_cache_enabled() is False


def test_cache_stays_enabled_if_the_caller_had_it_enabled(monkeypatch):
    osw_obj = _make_osw(cache_enabled=True)
    seen_states = []
    _stub_fetch_schema(monkeypatch, seen_states)

    osw_obj.fetch_schema(
        OSW.FetchSchemaParam(schema_title=["Category:Item", "Category:Entity"])
    )

    assert seen_states == [True, True]
    assert osw_obj.site.get_cache_enabled() is True


def test_a_worker_that_leaves_the_cache_enabled_does_not_leak(monkeypatch):
    """The reported defect: the per-title worker enabled the cache and kept it."""
    osw_obj = _make_osw(cache_enabled=False)
    seen_states = []
    _stub_fetch_schema(monkeypatch, seen_states, leaks=True)

    osw_obj.fetch_schema(
        OSW.FetchSchemaParam(schema_title=["Category:Item", "Category:Entity"])
    )

    assert osw_obj.site.get_cache_enabled() is False


def test_cache_is_restored_when_a_title_raises(monkeypatch):
    osw_obj = _make_osw(cache_enabled=False)
    seen_states = []
    _stub_fetch_schema(monkeypatch, seen_states, fail_on="Category:Entity", leaks=True)

    with pytest.raises(RuntimeError):
        osw_obj.fetch_schema(
            OSW.FetchSchemaParam(schema_title=["Category:Item", "Category:Entity"])
        )

    assert osw_obj.site.get_cache_enabled() is False


def test_cache_is_restored_when_the_last_title_returns_early(monkeypatch):
    """A missing schema page returns before the end of _fetch_schema()."""
    osw_obj = _make_osw(cache_enabled=False)

    def stub(self, fetchSchemaParam=None):
        # mirrors the early return for a page that does not exist, which happens
        # after the previous _fetch_schema() had enabled the cache
        self.site.enable_cache()
        return OSW.FetchSchemaResult(
            error_messages=[f"Page {fetchSchemaParam.schema_title} does not exist"]
        )

    monkeypatch.setattr(OSW, "_fetch_schema", stub)

    osw_obj.fetch_schema(
        OSW.FetchSchemaParam(schema_title=["Category:Item", "Category:Missing"])
    )

    assert osw_obj.site.get_cache_enabled() is False
