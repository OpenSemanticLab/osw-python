"""Tests for the store paths of the sync and the merge with stored page content."""

import json
import uuid
from types import SimpleNamespace
from typing import Any, Dict, Union

from opensemantic.base.v1 import User

from osw.core import OSW, OverwriteOptions
from osw.data.import_utility import uuid_to_full_page_title
from osw.tools.user_sync import sync as sync_module
from osw.tools.user_sync.build import apply_update, build_user
from osw.tools.user_sync.config import SyncConfig
from osw.tools.user_sync.interactive import Prompter
from osw.tools.user_sync.mapping import ProposedUser, user_uuid
from osw.tools.user_sync.prune import clear_jsondata_keys
from osw.tools.user_sync.sources import MwUser
from osw.tools.user_sync.sync import run_user_sync
from osw.wtsite import WtPage

ITEM_TITLE = "Item:OSWb0b1a0a0a0a04a0a8a0a0a0a0a0a0a01"


class FakeMwSite:
    def __init__(self, users):
        self._users = users

    def api(self, action, **params):
        return {"query": {"allusers": self._users}}


class FakeStoreOsw:
    """Fake connection whose store_entity returns the stage StoreEntityResult."""

    def __init__(self, users, existing=None, drop_username=False):
        self.mw_site = FakeMwSite(users)
        self.site = SimpleNamespace(semantic_search=self._semantic_search)
        self.existing = existing or {}
        self.drop_username = drop_username
        self.store_params = []

    def _semantic_search(self, param):
        titles = list(self.existing)
        return [
            SimpleNamespace(
                titles=titles, truncated=False, next_offset=None, count=len(titles)
            )
        ]

    def _get_missing_page_titles(self, titles, confirm_delay_s=5):
        return [t for t in titles if t not in self.existing]

    def load_entity(self, titles):
        if isinstance(titles, str):
            titles = [titles]
        loaded = []
        for title in titles:
            entity = self.existing.get(title)
            if entity is None:
                name = None if self.drop_username else "loaded"
                entity = SimpleNamespace(username=name)
            loaded.append(entity)
        return loaded

    def store_entity(self, param):
        self.store_params.append(param)
        return OSW.StoreEntityResult(change_id="c1", pages={})


def _run(osw, **config):
    config.setdefault("auto_apply", True)
    return run_user_sync(
        SyncConfig(domain="d", **config),
        osw=osw,
        prompter=Prompter(lambda prompt="": "y", lambda text="": None),
        session=None,
    )


def _patch_redirects(monkeypatch):
    written = []

    def fake_ensure(osw, username, item_title):
        written.append((username, item_title))
        return f"User:{username}"

    monkeypatch.setattr(sync_module, "ensure_redirect", fake_ensure)
    return written


def _title(username):
    return uuid_to_full_page_title(user_uuid(MwUser(name=username)))


def test_accepted_run_stores_and_writes_redirects(monkeypatch):
    written = _patch_redirects(monkeypatch)
    osw = FakeStoreOsw([
        {"name": "Alice", "groups": ["user"]},
        {"name": "Bob", "groups": ["user"]},
    ])
    report = _run(osw)
    assert report.accepted is True
    param = osw.store_params[0]
    assert param.overwrite == OverwriteOptions.true
    assert param.remove_empty is True
    assert report.created == [_title("Alice"), _title("Bob")]
    assert report.updated == []
    assert written == [("Alice", _title("Alice")), ("Bob", _title("Bob"))]
    assert report.redirects_created == ["User:Alice", "User:Bob"]
    assert report.failed == {}


def test_verify_reports_entity_without_username(monkeypatch):
    _patch_redirects(monkeypatch)
    osw = FakeStoreOsw([{"name": "Alice", "groups": ["user"]}], drop_username=True)
    report = _run(osw)
    assert "verify" in report.failed


def _existing_user():
    return SimpleNamespace(
        username="Alice",
        uuid=user_uuid(MwUser(name="Alice")),
        label=[SimpleNamespace(text="Alice")],
        first_name="Alice",
        surname="Alice",
        orcid=None,
        email=set(),
        website={"https://example.org"},
        __iris__={
            "organization": ["Item:OSWa"],
            "employment_contract_status": "Item:OSWb",
        },
    )


def test_prune_run_stores_with_default_and_clears_keys_afterwards(monkeypatch):
    _patch_redirects(monkeypatch)
    # the fake entity is not a model, so skip the pydantic validation of the param
    monkeypatch.setattr(
        sync_module,
        "OSW",
        SimpleNamespace(StoreEntityParam=lambda **kw: SimpleNamespace(**kw)),
    )
    cleared = []

    def fake_clear(osw, title, keys):
        cleared.append((title, sorted(keys)))
        return True

    monkeypatch.setattr(sync_module, "clear_jsondata_keys", fake_clear)
    existing = _existing_user()
    osw = FakeStoreOsw(
        [{"name": "Alice", "groups": ["user"]}], existing={ITEM_TITLE: existing}
    )
    report = _run(osw, prune=True)
    assert report.updated == [_title("Alice")]
    param = osw.store_params[0]
    assert not hasattr(param, "remove_empty")  # the store_entity default applies
    assert param.entities[0] is existing
    assert cleared == [
        (_title("Alice"), ["employment_contract_status", "organization", "website"])
    ]
    assert report.pruned == [_title("Alice")]
    assert "pruned=1" in report.summary()


def test_normal_run_never_clears_keys(monkeypatch):
    _patch_redirects(monkeypatch)
    monkeypatch.setattr(
        sync_module,
        "OSW",
        SimpleNamespace(StoreEntityParam=lambda **kw: SimpleNamespace(**kw)),
    )
    calls = []
    monkeypatch.setattr(
        sync_module, "clear_jsondata_keys", lambda *a, **k: calls.append(a)
    )
    osw = FakeStoreOsw(
        [{"name": "Alice", "groups": ["user"]}], existing={ITEM_TITLE: _existing_user()}
    )
    report = _run(osw)
    assert calls == []
    assert report.pruned == []


# --------------------------------------------------------------------------
# merge with the stored page on stage
# --------------------------------------------------------------------------


class OfflineWtPage(WtPage):
    """A WtPage that pretends to exist without touching a wiki."""

    def __init__(self, wtSite: Any = None, title: str = None):
        self.wtSite = wtSite
        self.title = title
        self.exists = True
        self._original_content = ""
        self.changed: bool = False
        self._dict = []
        self._slots: Dict[str, Union[str, dict]] = {"main": ""}
        self._slots_changed: Dict[str, bool] = {"main": False}
        self._content_model: Dict[str, str] = {"main": "wikitext"}


REMOTE_STATUS = "Item:OSWb"


def _proposed(user_id, **kw):
    args = dict(
        uuid=user_id,
        username="Alice",
        first_name="Alice",
        surname="Alice",
        label="Alice",
        orcid=None,
        emails=[],
        websites=[],
        organizations=[],
    )
    args.update(kw)
    return ProposedUser(**args)


def _json(entity):
    return json.loads(entity.json(exclude_none=True))


def test_built_user_has_no_employment_contract_status():
    user = build_user(_proposed(uuid.uuid4(), websites=["https://example.org"]))
    assert "employment_contract_status" not in _json(user)


def _loaded_user(user_id):
    return User(
        uuid=user_id,
        username="Alice",
        first_name="Alice",
        surname="Alice",
        label=[{"text": "Alice"}],
        website={"https://example.org"},
        organization=["Item:OSWa"],
    )


def test_normal_update_keeps_remote_employment_contract_status():
    user_id = uuid.uuid4()
    remote = {
        "type": ["Category:OSWd9aa0bca9b0040d8af6f5c091bf9eec7"],
        "uuid": str(user_id),
        "username": "Alice",
        "first_name": "Alice",
        "surname": "Alice",
        "label": [{"text": "Alice", "lang": "en"}],
        "organization": ["Item:OSWa"],
        "employment_contract_status": REMOTE_STATUS,
    }
    page = OfflineWtPage(title=uuid_to_full_page_title(user_id))
    page.set_slot_content("jsondata", dict(remote))
    entity = _loaded_user(user_id)
    apply_update(
        entity,
        _proposed(user_id, first_name="Alicia", websites=["https://example.org"]),
        {"first_name", "websites"},
    )
    assert "employment_contract_status" not in _json(entity)
    merged = OSW._apply_overwrite_policy(
        OSW._ApplyOverwriteParam(
            page=page, entity=entity, policy=True, inplace=False, remove_empty=True
        )
    ).get_slot_content("jsondata")
    assert merged["employment_contract_status"] == REMOTE_STATUS
    assert merged["first_name"] == "Alicia"


# --------------------------------------------------------------------------
# clear_jsondata_keys
# --------------------------------------------------------------------------


class FakePrunePage:
    """Stands in for WtPage: holds a jsondata slot and records the writes."""

    def __init__(self, content):
        self.content = content
        self.comments = []

    def get_slot_content(self, slot):
        assert slot == "jsondata"
        return json.loads(json.dumps(self.content))

    def set_slot_content(self, slot, content):
        assert slot == "jsondata"
        self.content = content

    def edit(self, comment=None):
        self.comments.append(comment)


def _patch_page(monkeypatch, page):
    from osw.tools.user_sync import prune

    monkeypatch.setattr(prune, "WtPage", lambda wtSite=None, title=None: page)


def test_clear_jsondata_keys_empties_present_keys_only(monkeypatch):
    content = {
        "website": ["https://example.org"],
        "organization": ["Item:OSWa"],
        "employment_contract_status": "Item:OSWb",
        "short_name": [{"text": "x", "lang": "en"}],
    }
    page = FakePrunePage(content)
    _patch_page(monkeypatch, page)
    written = clear_jsondata_keys(
        SimpleNamespace(site=None),
        ITEM_TITLE,
        ["website", "organization", "employment_contract_status"],
    )
    assert written is True
    assert page.content["website"] == []
    assert page.content["organization"] == []
    assert page.content["employment_contract_status"] == []
    assert page.content["short_name"] == content["short_name"]
    assert page.comments == ["user-sync: prune"]


def test_clear_jsondata_keys_does_not_add_absent_keys_or_write(monkeypatch):
    page = FakePrunePage({"website": [], "username": "Alice"})
    _patch_page(monkeypatch, page)
    written = clear_jsondata_keys(
        SimpleNamespace(site=None), ITEM_TITLE, ["website", "organization"]
    )
    assert written is False
    assert page.content == {"website": [], "username": "Alice"}
    assert page.comments == []
