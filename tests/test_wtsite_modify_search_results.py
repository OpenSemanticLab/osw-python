"""Unit tests for WtSite.modify_search_results().

Regression guard for #27: modify_search_results now accepts the previously
unused ModifySearchResultsParam object, gains an optional parallel mode, and
must keep the legacy keyword-argument call form working.
"""

import threading

import osw.wtsite as wtsite_mod
from osw.wtsite import WtPage, WtSite


class _FakeSite:
    """Stands in for mwclient.Site. No method on it should ever be touched."""

    host = "example.org"


def _make_fake_wtsite():
    """A WtSite that performs no network calls."""
    ws = WtSite.__new__(WtSite)
    ws._session_lock = threading.RLock()
    ws._site = _FakeSite()
    return ws


def _make_pages(wtsite, titles):
    return {
        title: WtPage(wtSite=wtsite, title=title, do_init=False) for title in titles
    }


def _stub_search(monkeypatch, titles):
    """Both prefix_search and semantic_search return the same fixed titles."""
    monkeypatch.setattr(wtsite_mod.wt, "prefix_search", lambda site, query: titles)
    monkeypatch.setattr(wtsite_mod.wt, "semantic_search", lambda site, query: titles)


def _stub_get_page(monkeypatch, ws, pages_by_title):
    """WtSite.get_page returns the canned page instead of hitting the network."""

    def fake_get_page(param):
        title = param.titles[0]
        return WtSite.GetPageResult(pages=[pages_by_title[title]], errors=[])

    monkeypatch.setattr(ws, "get_page", fake_get_page)


def _stub_edits(monkeypatch, pages_by_title, comments, lock=None):
    """Records (title, comment) for every page.edit() call instead of editing."""

    def make_recorder(page):
        def _edit(comment=None):
            if lock is not None:
                with lock:
                    comments.append((page.title, comment))
            else:
                comments.append((page.title, comment))

        return _edit

    for page in pages_by_title.values():
        monkeypatch.setattr(page, "edit", make_recorder(page))


def test_modify_search_results_with_param_object_sequential(monkeypatch):
    """The new param-object call form produces the same result as the old loop."""
    ws = _make_fake_wtsite()
    titles = ["Item:OSW1", "Item:OSW2", "Item:OSW3"]
    pages = _make_pages(ws, titles)
    comments = []

    _stub_search(monkeypatch, titles)
    _stub_get_page(monkeypatch, ws, pages)
    _stub_edits(monkeypatch, pages, comments)

    handled = []

    def modify_page(wtpage):
        handled.append(wtpage.title)

    param = WtSite.ModifySearchResultsParam(
        mode="prefix", query="Item:", comment="[bot] test", dryrun=False
    )
    ws.modify_search_results(param, modify_page=modify_page)

    assert handled == titles
    assert comments == [(title, "[bot] test") for title in titles]


def test_modify_search_results_parallel_processes_every_result(monkeypatch):
    """Every search result is handled when parallel processing is enabled."""
    ws = _make_fake_wtsite()
    titles = [f"Item:OSW{i}" for i in range(8)]
    pages = _make_pages(ws, titles)
    comments = []
    lock = threading.Lock()

    _stub_search(monkeypatch, titles)
    _stub_get_page(monkeypatch, ws, pages)
    _stub_edits(monkeypatch, pages, comments, lock=lock)

    handled = []

    def modify_page(wtpage):
        with lock:
            handled.append(wtpage.title)

    param = WtSite.ModifySearchResultsParam(
        mode="prefix",
        query="Item:",
        comment="[bot] parallel",
        parallel=True,
    )
    ws.modify_search_results(param, modify_page=modify_page)

    assert sorted(handled) == sorted(titles)
    assert sorted(comments) == sorted((title, "[bot] parallel") for title in titles)


def test_modify_search_results_legacy_keyword_call_still_works(monkeypatch):
    """The pre-existing positional/keyword call form is unchanged."""
    ws = _make_fake_wtsite()
    titles = ["Item:OSW1"]
    pages = _make_pages(ws, titles)
    comments = []

    _stub_search(monkeypatch, titles)
    _stub_get_page(monkeypatch, ws, pages)
    _stub_edits(monkeypatch, pages, comments)

    handled = []

    ws.modify_search_results(
        "prefix",
        "Item:",
        lambda wtpage: handled.append(wtpage.title),
        limit=1,
        comment="[bot] legacy",
        log=False,
        dryrun=False,
    )

    assert handled == titles
    assert comments == [("Item:OSW1", "[bot] legacy")]
