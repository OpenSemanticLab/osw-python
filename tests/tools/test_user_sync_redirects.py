"""Unit tests for redirect page handling."""

from osw.tools.user_sync import redirects
from osw.tools.user_sync.redirects import (
    ensure_redirect,
    is_redirect,
    redirect_wikitext,
)


def test_redirect_wikitext():
    assert redirect_wikitext("Item:OSW123") == "#REDIRECT [[Item:OSW123]]"


def test_is_redirect():
    assert is_redirect("#REDIRECT [[Item:OSW1]]")
    assert is_redirect("  #redirect [[x]]")
    assert not is_redirect("Some real user page content")


class FakeWtPage:
    exists_map: dict = {}
    content_map: dict = {}

    def __init__(self, wtSite=None, title=None, do_init=True):
        self.title = title
        self.exists = self.exists_map.get(title, False)
        self._content = self.content_map.get(title, "")
        self.written = None
        self.edited = False

    def get_slot_content(self, slot_key):
        return self._content

    def set_slot_content(self, slot_key, content):
        self.written = content

    def edit(self, comment=None):
        self.edited = True


class FakeOsw:
    site = object()


def _patch(monkeypatch, exists_map, content_map):
    FakeWtPage.exists_map = exists_map
    FakeWtPage.content_map = content_map
    monkeypatch.setattr(redirects, "WtPage", FakeWtPage)


def test_ensure_redirect_creates_missing(monkeypatch):
    _patch(monkeypatch, {}, {})
    written = ensure_redirect(FakeOsw(), "0000-0002-6374-9831", "Item:OSW1")
    assert written == "User:0000-0002-6374-9831"


def test_ensure_redirect_overwrites_existing_redirect(monkeypatch):
    title = "User:alice"
    _patch(monkeypatch, {title: True}, {title: "#REDIRECT [[Item:OSWold]]"})
    written = ensure_redirect(FakeOsw(), "alice", "Item:OSWnew")
    assert written == title


def test_ensure_redirect_skips_real_page(monkeypatch):
    title = "User:bob"
    _patch(monkeypatch, {title: True}, {title: "This is my real user page."})
    written = ensure_redirect(FakeOsw(), "bob", "Item:OSW1")
    assert written is None


def test_ensure_redirect_skips_when_already_correct(monkeypatch):
    title = "User:carol"
    _patch(monkeypatch, {title: True}, {title: "#REDIRECT [[Item:OSW1]]"})
    written = ensure_redirect(FakeOsw(), "carol", "Item:OSW1")
    assert written is None
