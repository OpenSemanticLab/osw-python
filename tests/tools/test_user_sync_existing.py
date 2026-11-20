"""Unit tests for loading and indexing existing User items."""

from types import SimpleNamespace

import pytest

from osw import wiki_tools
from osw.tools.user_sync.existing import (
    ExistingUsers,
    adopt_existing_pages,
    load_existing_users,
)
from osw.wtsite import WtPage


class FakeWtPage(WtPage):
    """A WtPage that serves a fixed jsondata slot without a wiki."""

    def __init__(self, title, jsondata=None):
        self.title = title
        self._jsondata = jsondata or {}

    def get_slot_content(self, slot, *args, **kwargs):
        return self._jsondata


def _ask_result(titles, continue_offset=None):
    """An SMW ``ask`` response as wiki_tools.semantic_search reads it."""
    result = {
        "query": {
            "results": {
                title: {"fulltext": title, "exists": "1", "printouts": {}}
                for title in titles
            }
        }
    }
    if continue_offset is not None:
        result["query-continue-offset"] = continue_offset
    return result


class FakeSite:
    """Answers ``ask`` with the given responses, one per request, in order."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.queries = []
        self.stored = {}

    def get_page(self, param):
        pages = [FakeWtPage(t, self.stored.get(t, {"uuid": t})) for t in param.titles]
        return SimpleNamespace(pages=pages, errors=[])

    def api(self, action, **params):
        assert action == "ask"
        self.queries.append(params["query"])
        return self._responses[len(self.queries) - 1]

    def semantic_search(self, query):
        return wiki_tools.semantic_search(self, query)


class FakeOsw:
    def __init__(self, titles, entities, pages=None, missing=()):
        self._entities = entities
        self.site = FakeSite(pages or [_ask_result(titles)])
        self.missing = set(missing)
        self.loaded = None

    def _get_missing_page_titles(self, titles, confirm_delay_s=5):
        assert confirm_delay_s == 0
        return [t for t in titles if t in self.missing]

    def load_entity(self, param):
        titles = param.titles
        self.loaded = list(titles)
        assert set(param.offline_pages) == set(titles)
        return [self._entities[t] for t in titles]


def test_load_indexes_by_username():
    entities = {
        "Item:OSW1": SimpleNamespace(username="0000-0002-6374-9831"),
        "Item:OSW2": SimpleNamespace(username="Alice"),
    }
    osw = FakeOsw(["Item:OSW1", "Item:OSW2"], entities)
    existing = load_existing_users(osw)
    assert set(existing.by_username) == {"0000-0002-6374-9831", "Alice"}
    assert existing.get("Alice") is entities["Item:OSW2"]
    assert existing.get("missing") is None


def test_load_empty():
    osw = FakeOsw([], {})
    existing = load_existing_users(osw)
    assert existing.by_username == {}


def test_load_skips_entities_without_username():
    entities = {
        "Item:OSW1": SimpleNamespace(username=None),
        "Item:OSW2": SimpleNamespace(username="Bob"),
    }
    osw = FakeOsw(["Item:OSW1", "Item:OSW2"], entities)
    existing = load_existing_users(osw)
    assert set(existing.by_username) == {"Bob"}


def test_load_respects_limit():
    entities = {
        "Item:OSW1": SimpleNamespace(username="A"),
        "Item:OSW2": SimpleNamespace(username="B"),
    }
    osw = FakeOsw(["Item:OSW1", "Item:OSW2"], entities)
    existing = load_existing_users(osw, limit=1)
    assert osw.loaded == ["Item:OSW1"]
    assert set(existing.by_username) == {"A"}


def test_load_pages_through_all_results_with_the_reported_offset():
    entities = {
        "Item:OSW1": SimpleNamespace(username="A"),
        "Item:OSW2": SimpleNamespace(username="B"),
        "Item:OSW3": SimpleNamespace(username="C"),
    }
    # the wiki cuts the first page at 2 results and reports offset 2
    pages = [
        _ask_result(["Item:OSW1", "Item:OSW2"], continue_offset=2),
        _ask_result(["Item:OSW3"]),
    ]
    osw = FakeOsw([], entities, pages=pages)
    existing = load_existing_users(osw)
    assert set(existing.by_username) == {"A", "B", "C"}
    assert len(osw.site.queries) == 2
    assert "|offset=0" in osw.site.queries[0]
    assert "|offset=2" in osw.site.queries[1]
    assert osw.loaded == ["Item:OSW1", "Item:OSW2", "Item:OSW3"]


def test_load_raises_when_the_reported_offset_does_not_advance():
    pages = [
        _ask_result(["Item:OSW1"], continue_offset=0),
        _ask_result(["Item:OSW1"], continue_offset=0),
    ]
    osw = FakeOsw([], {}, pages=pages)
    with pytest.raises(RuntimeError, match="offset"):
        load_existing_users(osw)
    assert len(osw.site.queries) == 1


def _proposed(username, uid):
    return SimpleNamespace(
        username=username,
        uuid=uid,
        full_page_title=f"Item:OSW{uid}",
    )


def test_adopt_loads_a_page_that_exists_at_the_deterministic_title():
    found = SimpleNamespace(username=None, uuid="1")
    osw = FakeOsw(
        [], {"Item:OSW1": found}, pages=[_ask_result([])], missing={"Item:OSW2"}
    )
    existing = ExistingUsers()
    adopted = adopt_existing_pages(
        osw, existing, [_proposed("Alice", "1"), _proposed("Bob", "2")]
    )
    assert adopted == ["Item:OSW1"]
    assert osw.loaded == ["Item:OSW1"]
    assert existing.get("Alice") is found
    assert existing.get("Bob") is None


def test_adopt_skips_users_already_matched_by_username():
    osw = FakeOsw([], {}, pages=[_ask_result([])])
    existing = ExistingUsers(by_username={"Alice": SimpleNamespace(username="Alice")})
    assert adopt_existing_pages(osw, existing, [_proposed("Alice", "1")]) == []
    assert osw.loaded is None


def test_load_records_the_stored_jsondata_per_username():
    entities = {
        "Item:OSW1": SimpleNamespace(username="Alice", uuid="u1"),
        "Item:OSW2": SimpleNamespace(username="Bob", uuid="u2"),
    }
    osw = FakeOsw(["Item:OSW1", "Item:OSW2"], entities)
    osw.site.stored = {
        "Item:OSW1": {"uuid": "u1", "username": "Alice", "website": []},
        "Item:OSW2": {"uuid": "u2", "username": "Bob"},
    }
    existing = load_existing_users(osw)
    assert existing.get_stored("Alice") == osw.site.stored["Item:OSW1"]
    assert "employment_contract_status" not in existing.get_stored("Bob")
    assert existing.get_stored("missing") is None


def test_adopt_records_the_stored_jsondata():
    found = SimpleNamespace(username=None, uuid="1")
    osw = FakeOsw([], {"Item:OSW1": found}, pages=[_ask_result([])])
    osw.site.stored = {"Item:OSW1": {"uuid": "1", "label": [{"text": "A"}]}}
    existing = ExistingUsers()
    adopt_existing_pages(osw, existing, [_proposed("Alice", "1")])
    assert existing.get_stored("Alice") == osw.site.stored["Item:OSW1"]
