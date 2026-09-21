"""Unit tests for the cache-state restore in load_entity().

Regression guard for #183: https://github.com/OpenSemanticLab/osw-python/issues/183
load_entity() saved the original cache state before fetching pages and restored
it afterwards, but the restore was not in a finally block. An exception raised
while fetching or parsing a page left the cache enabled (or disabled) for the
rest of the process instead of restoring the state the caller had before the
call.

These run fully offline: the fake site never touches the network.
"""

from types import SimpleNamespace

import pytest

from osw.core import OSW


class _FakeSite:
    def __init__(self, cache_enabled, pages=None, fails=False):
        self.cache_enabled = cache_enabled
        self._pages = pages if pages is not None else []
        self.fails = fails

    def get_cache_enabled(self):
        return self.cache_enabled

    def enable_cache(self):
        self.cache_enabled = True

    def disable_cache(self):
        self.cache_enabled = False

    def get_page(self, param):
        if self.fails:
            raise RuntimeError("the wiki is not reachable")
        return SimpleNamespace(pages=self._pages)


@pytest.mark.parametrize("disable_cache", [False, True])
def test_cache_stays_disabled_when_get_page_raises(disable_cache):
    site = _FakeSite(cache_enabled=False, fails=True)
    osw_obj = OSW.construct(site=site)

    with pytest.raises(RuntimeError):
        osw_obj.load_entity(
            OSW.LoadEntityParam(titles=["Item:Foo"], disable_cache=disable_cache)
        )

    assert site.get_cache_enabled() is False


@pytest.mark.parametrize("disable_cache", [False, True])
def test_cache_stays_enabled_when_get_page_raises(disable_cache):
    site = _FakeSite(cache_enabled=True, fails=True)
    osw_obj = OSW.construct(site=site)

    with pytest.raises(RuntimeError):
        osw_obj.load_entity(
            OSW.LoadEntityParam(titles=["Item:Foo"], disable_cache=disable_cache)
        )

    assert site.get_cache_enabled() is True


class _FailingPage:
    """A page whose slot content cannot be read.

    Raises from inside the per-page loop rather than from get_page, so that the
    try block is shown to cover the whole body and not only its first call.
    """

    title = "Item:Foo"

    def get_slot_content(self, slot):
        raise RuntimeError("the slot content is not readable")


@pytest.mark.parametrize("cache_enabled", [False, True])
def test_cache_is_restored_when_the_page_loop_raises(cache_enabled):
    site = _FakeSite(cache_enabled=cache_enabled, pages=[_FailingPage()])
    osw_obj = OSW.construct(site=site)

    with pytest.raises(RuntimeError):
        osw_obj.load_entity(
            OSW.LoadEntityParam(titles=["Item:Foo"], disable_cache=True)
        )

    assert site.get_cache_enabled() is cache_enabled


def test_cache_state_is_restored_after_normal_path_disabled():
    site = _FakeSite(cache_enabled=False)
    osw_obj = OSW.construct(site=site)

    osw_obj.load_entity(OSW.LoadEntityParam(titles=["Item:Foo"]))

    assert site.get_cache_enabled() is False


def test_cache_state_is_restored_after_normal_path_enabled():
    site = _FakeSite(cache_enabled=True)
    osw_obj = OSW.construct(site=site)

    osw_obj.load_entity(OSW.LoadEntityParam(titles=["Item:Foo"]))

    assert site.get_cache_enabled() is True
