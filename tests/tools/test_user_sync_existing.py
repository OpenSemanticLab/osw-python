"""Unit tests for loading and indexing existing User items."""

from types import SimpleNamespace

from osw.tools.user_sync.existing import load_existing_users


class FakeOsw:
    def __init__(self, titles, entities):
        self._titles = titles
        self._entities = entities
        self.loaded = None

    def query_instances(self, category):
        assert category.startswith("Category:OSW")
        return list(self._titles)

    def load_entity(self, titles):
        self.loaded = list(titles)
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
