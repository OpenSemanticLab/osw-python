"""Unit tests for WtSite.get_allowed_file_extensions and its cache.

These tests construct a WtSite without going through __init__ (which would
require network / credentials) and exercise the cache mechanics directly
against a fake mwclient site.
"""

from datetime import datetime, timedelta

from osw.wtsite import WtSite


class _FakeMwSite:
    """Stands in for the mwclient.Site behind WtSite.mw_site."""

    host = "wiki.example.org"

    def __init__(self, extensions=None, fail=False, payload=None):
        self._extensions = extensions or []
        self._fail = fail
        self._payload = payload
        self.api_calls = 0
        self.calls = []
        """the (args, kwargs) of every api() call, to check the request sent"""

    def api(self, *args, **kwargs):
        self.api_calls += 1
        self.calls.append((args, kwargs))
        if self._fail:
            raise RuntimeError("siteinfo unavailable")
        if self._payload is not None:
            return self._payload
        return {"query": {"fileextensions": [{"ext": e} for e in self._extensions]}}


def _fake_site(extensions=None, fail=False, payload=None):
    """Builds a minimal WtSite carrying a fake mwclient site, bypassing __init__."""
    ws = WtSite.__new__(WtSite)
    ws._site = _FakeMwSite(extensions=extensions, fail=fail, payload=payload)
    ws._allowed_file_extensions = None
    return ws


def test_reads_the_extensions_from_siteinfo_and_returns_a_fetched_at():
    site = _fake_site(extensions=["png", "pdf"])

    result = site.get_allowed_file_extensions()

    assert result.extensions == ["png", "pdf"]
    assert isinstance(result.fetched_at, datetime)


def test_a_second_call_returns_the_cached_value_without_querying_the_wiki_again():
    site = _fake_site(extensions=["png", "pdf"])

    first = site.get_allowed_file_extensions()
    second = site.get_allowed_file_extensions()

    assert second is first
    assert site.mw_site.api_calls == 1


def test_refresh_true_re_reads_and_updates_fetched_at():
    site = _fake_site(extensions=["png"])

    first = site.get_allowed_file_extensions()
    second = site.get_allowed_file_extensions(refresh=True)

    assert site.mw_site.api_calls == 2
    assert second.fetched_at >= first.fetched_at


def test_an_entry_older_than_the_ttl_is_re_read():
    site = _fake_site(extensions=["png"])
    site.get_allowed_file_extensions()
    site._allowed_file_extensions.fetched_at = datetime.now() - timedelta(hours=25)

    site.get_allowed_file_extensions()

    assert site.mw_site.api_calls == 2


def test_an_entry_23_hours_old_is_still_served_from_the_cache():
    site = _fake_site(extensions=["png"])
    site.get_allowed_file_extensions()
    site._allowed_file_extensions.fetched_at = datetime.now() - timedelta(hours=23)

    site.get_allowed_file_extensions()

    assert site.mw_site.api_calls == 1


def test_clear_allowed_file_extensions_cache_forces_a_re_read():
    site = _fake_site(extensions=["png"])
    site.get_allowed_file_extensions()

    site.clear_allowed_file_extensions_cache()
    site.get_allowed_file_extensions()

    assert site.mw_site.api_calls == 2


def test_a_failing_lookup_returns_none_and_is_not_cached():
    """A failed lookup must not poison the cache: a later successful call must
    still return the real list, not the failure."""
    site = _fake_site(fail=True)

    failed = site.get_allowed_file_extensions()

    assert failed.extensions is None
    assert failed.fetched_at is None

    site.mw_site._fail = False
    site.mw_site._extensions = ["png"]
    succeeded = site.get_allowed_file_extensions()

    assert succeeded.extensions == ["png"]


def test_a_wtsite_without_the_attribute_set_at_all_still_works():
    """A WtSite built via __new__ may not have _allowed_file_extensions set,
    the getattr fallback in get_allowed_file_extensions must handle that."""
    ws = WtSite.__new__(WtSite)
    ws._site = _FakeMwSite(extensions=["png"])

    result = ws.get_allowed_file_extensions()

    assert result.extensions == ["png"]


def test_the_request_sent_matches_the_siteinfo_fileextensions_query():
    """A typo in the action, meta or siprop would otherwise pass unnoticed."""
    site = _fake_site(extensions=["png"])

    site.get_allowed_file_extensions()

    args, kwargs = site.mw_site.calls[0]
    assert args == ("query",)
    assert kwargs == {
        "meta": "siteinfo",
        "siprop": "fileextensions",
        "formatversion": 2,
    }


def test_a_malformed_siteinfo_payload_returns_none_instead_of_raising():
    """fileextensions entries that are not mappings must not crash the lookup,
    since it only ever enriches an error message."""
    site = _fake_site(payload={"query": {"fileextensions": [1, 2, 3]}})

    result = site.get_allowed_file_extensions()

    assert result.extensions is None
    assert result.fetched_at is None
