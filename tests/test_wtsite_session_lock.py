"""Unit tests for WtSite session-state concurrency hardening (Fix B1).

These tests construct a WtSite without going through ``__init__`` (which would
require network / credentials) and exercise ``_clear_cookies`` directly against a
real ``requests`` cookie jar.
"""

import threading
import types

import requests.cookies as rc

from osw.wtsite import WtSite


def _make_wtsite_with_jar():
    """Build a minimal WtSite carrying a real cookie jar, bypassing __init__."""
    jar = rc.RequestsCookieJar()
    fake_site = types.SimpleNamespace(connection=types.SimpleNamespace(cookies=jar))
    ws = WtSite.__new__(WtSite)
    ws._session_lock = threading.RLock()
    ws._site = fake_site
    return ws, jar


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


def test_clear_cookies_under_concurrency_is_safe():
    """Concurrent clears + reads must not raise and must preserve unrelated cookies."""
    ws, jar = _make_wtsite_with_jar()
    _populate(jar)

    errors = []
    stop = threading.Event()

    def clearer():
        try:
            for _ in range(200):
                # re-add under the lock so there is always something to clear,
                # creating real contention with the concurrent _clear_cookies calls
                with ws._session_lock:
                    for i in range(25):
                        jar.set(
                            f"PostEditRevision{i}",
                            f"v{i}",
                            domain="example.org",
                            path="/",
                        )
                ws._clear_cookies()
        except Exception as exc:  # noqa: BLE001 - collected and asserted below
            errors.append(exc)

    def reader():
        try:
            while not stop.is_set():
                _ = [c.name for c in list(jar)]
        except Exception as exc:  # noqa: BLE001 - collected and asserted below
            errors.append(exc)

    clearers = [threading.Thread(target=clearer) for _ in range(4)]
    readers = [threading.Thread(target=reader) for _ in range(2)]
    for t in readers:
        t.start()
    for t in clearers:
        t.start()
    for t in clearers:
        t.join()
    stop.set()
    for t in readers:
        t.join()

    assert errors == []
    # the non-PostEditRevision cookie must survive every clear
    assert "sessionToken" in {c.name for c in jar}
