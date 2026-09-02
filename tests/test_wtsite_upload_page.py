"""Unit tests for WtSite.upload_page().

Regression guard for #112: an edit comment supplied via UploadPageParam must
reach WtPage.edit(), so bulk uploads are attributable in the page history.
"""

import threading

from osw.wtsite import WtPage, WtSite


class _FakeSite:
    """Stands in for mwclient.Site, only get_url() touches it."""

    host = "example.org"


def _make_fake_wtsite():
    """A WtSite that performs no network calls."""
    ws = WtSite.__new__(WtSite)
    ws._session_lock = threading.RLock()
    ws._site = _FakeSite()
    return ws


def _make_page(wtsite, title, recorder, monkeypatch):
    page = WtPage(wtSite=wtsite, title=title, do_init=False)
    monkeypatch.setattr(page, "edit", lambda comment=None: recorder.append(comment))
    return page


def test_upload_page_forwards_comment(monkeypatch):
    ws = _make_fake_wtsite()
    comments = []
    page = _make_page(ws, "Item:OSW123", comments, monkeypatch)

    ws.upload_page(WtSite.UploadPageParam(pages=page, comment="[bot edit] import"))

    assert comments == ["[bot edit] import"]


def test_upload_page_forwards_comment_to_every_page(monkeypatch):
    ws = _make_fake_wtsite()
    comments = []
    pages = [_make_page(ws, f"Item:OSW{i}", comments, monkeypatch) for i in range(3)]

    ws.upload_page(WtSite.UploadPageParam(pages=pages, comment="same for all"))

    assert comments == ["same for all"] * 3


def test_upload_page_without_comment_passes_none(monkeypatch):
    """Default behaviour is unchanged: edit() is called with no comment."""
    ws = _make_fake_wtsite()
    comments = []
    page = _make_page(ws, "Item:OSW123", comments, monkeypatch)

    ws.upload_page(page)

    assert comments == [None]
