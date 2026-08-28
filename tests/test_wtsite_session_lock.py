"""Unit tests for WtSite session-state concurrency hardening (Fix B1).

These tests construct a WtSite without going through ``__init__`` (which would
require network / credentials) and exercise ``_clear_cookies`` directly against a
real ``requests`` cookie jar.
"""

import threading
import types
from copy import deepcopy

import requests.cookies as rc

from osw.wtsite import WtPage, WtSite


def _make_wtsite_for(jar):
    """Wrap an arbitrary cookie jar in a minimal WtSite, bypassing __init__."""
    fake_site = types.SimpleNamespace(connection=types.SimpleNamespace(cookies=jar))
    ws = WtSite.__new__(WtSite)
    ws._session_lock = threading.RLock()
    ws._site = fake_site
    return ws


def _make_wtsite_with_jar():
    """Build a minimal WtSite carrying a real cookie jar, bypassing __init__."""
    jar = rc.RequestsCookieJar()
    return _make_wtsite_for(jar), jar


def _populate(jar, n=25):
    for i in range(n):
        jar.set(f"PostEditRevision{i}", f"v{i}", domain="example.org", path="/")
    # a cookie that must never be removed by _clear_cookies
    jar.set("sessionToken", "keep-me", domain="example.org", path="/")


def test_clear_cookies_removes_only_post_edit_revision():
    ws, jar = _make_wtsite_with_jar()
    _populate(jar)

    ws._clear_cookies()

    assert {c.name for c in jar} == {"sessionToken"}


def _fake_cookie(name):
    return types.SimpleNamespace(name=name, domain="example.org", path="/")


class _FakeJar:
    """Stands in for a jar being mutated by requests while we iterate it."""

    def __init__(self, entries):
        self._entries = entries
        self.cleared = []

    def __iter__(self):
        return iter(self._entries)

    def clear(self, domain, path, name):
        self.cleared.append((domain, path, name))


def test_clear_cookies_skips_none_entries_from_the_jar():
    """py<=3.10 http.cookiejar yields None for a cookie deleted mid-iteration.

    Its deepvalues() walks a lazy map(dict.get, sorted(keys)), so a concurrent
    delete turns into a None rather than a missing entry. Without the guard this
    raises AttributeError: 'NoneType' object has no attribute 'name'.
    """
    jar = _FakeJar([None, _fake_cookie("PostEditRevision1"), None])
    ws = _make_wtsite_for(jar)

    ws._clear_cookies()

    assert jar.cleared == [("example.org", "/", "PostEditRevision1")]


def test_clear_cookies_tolerates_a_cookie_already_removed():
    """CookieJar.clear raises KeyError if a peer deleted the cookie first.

    _clear_cookies works off a snapshot, so any entry may be gone by the time it
    calls clear(). It must swallow that and keep going, not abort the sweep.
    """

    class _RacingJar(_FakeJar):
        def clear(self, domain, path, name):
            super().clear(domain, path, name)
            raise KeyError(name)

    jar = _RacingJar([
        _fake_cookie("PostEditRevision1"),
        _fake_cookie("PostEditRevision2"),
    ])
    ws = _make_wtsite_for(jar)

    ws._clear_cookies()

    # the KeyError on the first cookie must not stop the second from being tried
    assert len(jar.cleared) == 2


def test_clear_cookies_under_concurrency_is_safe():
    """_clear_cookies must survive jar writes the session lock does not cover.

    requests' own extract_cookies() runs on every response and drops any cookie
    whose Set-Cookie expiry is in the past, taking only the jar's internal lock.
    So it races _clear_cookies two ways: the delete can land between the
    snapshot and the follow-up clear() (KeyError, any version), and on py<=3.10
    http.cookiejar iterates via a lazy map(dict.get, sorted(keys)), so the
    snapshot yields None instead of the deleted cookie.

    Only _clear_cookies is asserted on. Unsynchronized iteration of the jar is
    not something WtSite can make safe, since requests never takes the session
    lock, so the reader here is a contention generator and nothing more.
    """
    ws, jar = _make_wtsite_with_jar()
    _populate(jar)

    clear_errors = []
    stop = threading.Event()

    def peer_writer():
        """Stand in for requests.extract_cookies: set + delete, no session lock."""
        while not stop.is_set():
            for i in range(25):
                jar.set(f"PostEditRevision{i}", f"v{i}", domain="example.org", path="/")
            for i in range(25):
                try:
                    jar.clear("example.org", "/", f"PostEditRevision{i}")
                except KeyError:
                    pass

    def clearer():
        try:
            for _ in range(200):
                ws._clear_cookies()
        except Exception as exc:
            clear_errors.append(exc)

    def reader():
        while not stop.is_set():
            try:
                _ = [c.name for c in list(jar) if c is not None]
            except RuntimeError:
                # dict resized mid-iteration; the stdlib jar is not thread-safe
                pass

    peers = [threading.Thread(target=peer_writer, daemon=True) for _ in range(2)]
    readers = [threading.Thread(target=reader, daemon=True) for _ in range(2)]
    clearers = [threading.Thread(target=clearer) for _ in range(4)]
    for t in peers + readers:
        t.start()
    for t in clearers:
        t.start()
    for t in clearers:
        t.join()
    stop.set()
    for t in peers + readers:
        t.join()

    assert clear_errors == []
    # the non-PostEditRevision cookie must survive every clear
    assert "sessionToken" in {c.name for c in jar}


def test_wtsite_survives_deepcopy_of_a_page():
    """store_entity deep-copies the page, reaching WtSite through page.wtSite.

    Without WtSite.__getstate__ dropping the lock this raises
    TypeError: cannot pickle '_thread.RLock' object.
    """
    ws, jar = _make_wtsite_with_jar()
    _populate(jar)
    page = WtPage.__new__(WtPage)
    page.wtSite = ws
    page._slots = {"jsondata": {"uuid": "abc"}}

    copied = deepcopy(page)

    assert copied._slots == page._slots
    assert copied._slots is not page._slots
    # the copy has no lock until something asks for one
    assert "_session_lock" not in copied.wtSite.__dict__
    assert copied.wtSite._get_session_lock() is not ws._session_lock
