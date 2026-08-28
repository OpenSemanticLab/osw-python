"""Unit tests for WtPage.edit() retry/re-raise behavior (Fix A).

Regression guard: previously edit() returned None after exhausting its retries,
silently discarding the last exception. It must now raise so callers (and
store_entity) can see the failure.
"""

import threading

import pytest

import osw.wtsite as wtsite_mod
from osw.wtsite import WtPage, WtSite


class _FakeSite:
    def get_token(self, *args, **kwargs):
        raise RuntimeError("token refresh failed")


def _make_fake_wtsite():
    """A WtSite whose recovery hooks all fail, bypassing __init__ (no network)."""
    ws = WtSite.__new__(WtSite)
    ws._session_lock = threading.RLock()
    ws._site = _FakeSite()

    def _relogin_fails():
        raise RuntimeError("relogin failed")

    ws._relogin = _relogin_fails
    return ws


def test_edit_reraises_after_max_retries(monkeypatch):
    monkeypatch.setattr(wtsite_mod, "sleep", lambda *a, **k: None)

    ws = _make_fake_wtsite()
    page = WtPage(wtSite=ws, title="Item:OSW123", do_init=False)

    original_error = ValueError("edit boom")
    attempts = {"n": 0}

    def always_raise(*args, **kwargs):
        attempts["n"] += 1
        raise original_error

    monkeypatch.setattr(page, "_edit", always_raise)

    with pytest.raises(RuntimeError) as exc_info:
        page.edit()

    assert attempts["n"] == 5  # all max_retry attempts were made
    # the original exception must be chained, not discarded
    assert exc_info.value.__cause__ is original_error
    assert "Item:OSW123" in str(exc_info.value)


def test_edit_returns_result_on_success(monkeypatch):
    monkeypatch.setattr(wtsite_mod, "sleep", lambda *a, **k: None)
    ws = _make_fake_wtsite()
    page = WtPage(wtSite=ws, title="Item:OSW123", do_init=False)
    monkeypatch.setattr(page, "_edit", lambda *a, **k: "ok")

    assert page.edit() == "ok"


def test_edit_succeeds_after_transient_failures(monkeypatch):
    monkeypatch.setattr(wtsite_mod, "sleep", lambda *a, **k: None)
    ws = _make_fake_wtsite()
    page = WtPage(wtSite=ws, title="Item:OSW123", do_init=False)

    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return "done"

    monkeypatch.setattr(page, "_edit", flaky)

    assert page.edit() == "done"
    assert calls["n"] == 3
