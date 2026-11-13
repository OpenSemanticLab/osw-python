"""Failed and partial stores in an accepted sync run (issue 224).

The model builders, the redirect writer and the plan are replaced with fakes,
so these tests run the orchestrator without a wiki connection.
"""

import uuid
from types import SimpleNamespace

import pytest

from osw.core import OSW
from osw.tools.user_sync import sync
from osw.tools.user_sync.config import SyncConfig
from osw.tools.user_sync.interactive import Prompter, Resolution, ResolvedChange
from osw.tools.user_sync.mapping import ProposedOrganization, ProposedUser
from osw.tools.user_sync.reconcile import REMOVE, FieldDiff, UserChange


def _user(name, organizations=()):
    return ProposedUser(
        uuid=uuid.uuid5(uuid.NAMESPACE_DNS, name),
        username=name,
        first_name=name,
        surname=name,
        label=name,
        emails=[f"{name}@example.org"],
        organizations=list(organizations),
    )


def _org(name):
    return ProposedOrganization(uuid=uuid.uuid5(uuid.NAMESPACE_URL, name), name=name)


def _resolved(user, action):
    existing = None if action == "create" else SimpleNamespace(username=user.username)
    category = "new" if action == "create" else "gap_fill"
    return ResolvedChange(UserChange(user, existing, category), action, set())


def _partial_error(stored, failed):
    result = OSW.StoreEntityResult.construct(
        change_id="c",
        pages={t: object() for t in stored},
        failed={t: RuntimeError(f"boom {t}") for t in failed},
    )
    return OSW.StoreEntityPartialError(result)


class FakeOsw:
    """Records every store call; ``outcomes`` maps an edit comment to an outcome."""

    def __init__(self, outcomes=None):
        self.outcomes = outcomes or {}
        self.stored_payloads = {}

    def store_entity(self, param):
        titles = [e.title for e in param.entities]
        self.stored_payloads[param.edit_comment] = list(param.entities)
        outcome = self.outcomes.get(param.edit_comment)
        if callable(outcome):
            raise outcome(titles)
        if isinstance(outcome, Exception):
            raise outcome

    def load_entity(self, titles):
        return [SimpleNamespace(username="u") for _ in titles]


@pytest.fixture
def run(monkeypatch):
    """Run an accepted sync over a fixed plan and return (report, redirects)."""

    def _run(osw, resolved, org_map=None, **config):
        redirects = []
        users = [r.change.proposed for r in resolved]
        monkeypatch.setattr(
            sync, "_build_proposals", lambda c, o, s: (users, org_map or {}, [])
        )
        monkeypatch.setattr(sync, "adopt_existing_pages", lambda *a: None)
        # The real StoreEntityParam validates entities; the fakes are plain objects.
        monkeypatch.setattr(
            sync,
            "OSW",
            SimpleNamespace(
                StoreEntityParam=SimpleNamespace,
                StoreEntityPartialError=OSW.StoreEntityPartialError,
            ),
        )
        monkeypatch.setattr(sync, "load_existing_users", lambda o: None)
        monkeypatch.setattr(sync, "reconcile", lambda *a, **k: None)
        monkeypatch.setattr(
            sync,
            "resolve_plan",
            lambda *a, **k: Resolution(resolved=resolved, accepted=True),
        )
        monkeypatch.setattr(
            sync,
            "build_user",
            lambda p: SimpleNamespace(
                title=p.full_page_title, organization=list(p.organizations)
            ),
        )
        monkeypatch.setattr(
            sync,
            "apply_update",
            lambda e, p, f: SimpleNamespace(
                title=p.full_page_title, organization=list(p.organizations)
            ),
        )
        monkeypatch.setattr(
            sync,
            "build_organization",
            lambda o: SimpleNamespace(title=o.full_page_title),
        )

        def fake_redirect(osw_, username, title):
            redirects.append(title)
            return f"User:{username}"

        monkeypatch.setattr(sync, "ensure_redirect", fake_redirect)
        report = sync.run_user_sync(
            SyncConfig(domain="d", auto_apply=True, **config),
            osw=osw,
            prompter=Prompter(lambda p="": "y", lambda t="": None),
        )
        return report, redirects

    return _run


def test_partial_store_counts_only_stored_titles(run):
    ok, bad = _user("ok"), _user("bad")
    osw = FakeOsw({
        "user-sync": lambda titles: _partial_error(
            stored=[ok.full_page_title], failed=[bad.full_page_title]
        )
    })
    report, _ = run(osw, [_resolved(ok, "create"), _resolved(bad, "create")])
    assert report.created == [ok.full_page_title]
    assert f"store:{bad.full_page_title}" in report.failed


def test_failed_store_counts_nothing_as_created_or_updated(run):
    new, old = _user("new"), _user("old")
    osw = FakeOsw({"user-sync": RuntimeError("down")})
    report, _ = run(osw, [_resolved(new, "create"), _resolved(old, "update")])
    assert report.created == []
    assert report.updated == []
    assert "store" in report.failed


def test_no_redirect_for_a_created_item_that_was_not_stored(run):
    ok, bad, old = _user("ok"), _user("bad"), _user("old")
    osw = FakeOsw({
        "user-sync": lambda titles: _partial_error(
            stored=[ok.full_page_title],
            failed=[bad.full_page_title, old.full_page_title],
        )
    })
    _, redirects = run(
        osw,
        [_resolved(ok, "create"), _resolved(bad, "create"), _resolved(old, "update")],
    )
    # ``old`` already existed, so its redirect target exists even though the
    # update failed. ``bad`` was never stored.
    assert sorted(redirects) == sorted([ok.full_page_title, old.full_page_title])


def test_user_is_not_stored_with_a_link_to_a_failed_organization(run):
    org = _org("Acme")
    linked = _user("linked", organizations=[org.full_page_title])
    osw = FakeOsw({"user-sync: orgs": RuntimeError("down")})
    report, _ = run(
        osw,
        [_resolved(linked, "create")],
        org_map={org.uuid: org},
        link_organizations=True,
    )
    assert report.organizations == []
    stored = osw.stored_payloads.get("user-sync", [])
    assert "user-sync: orgs" in osw.stored_payloads
    assert all(org.full_page_title not in e.organization for e in stored)
    # The user itself is still stored, counted and redirected.
    assert report.created == [linked.full_page_title]
    assert report.redirects_created == ["User:linked"]


def test_partial_organization_store_drops_only_the_failed_link(run):
    good, gone = _org("Good"), _org("Gone")
    linked = _user("linked", organizations=[good.full_page_title, gone.full_page_title])
    osw = FakeOsw({
        "user-sync: orgs": lambda titles: _partial_error(
            stored=[good.full_page_title], failed=[gone.full_page_title]
        )
    })
    report, _ = run(
        osw,
        [_resolved(linked, "create")],
        org_map={good.uuid: good, gone.uuid: gone},
        link_organizations=True,
    )
    assert report.organizations == [good.full_page_title]
    assert f"store:{gone.full_page_title}" in report.failed
    (stored,) = osw.stored_payloads["user-sync"]
    assert stored.organization == [good.full_page_title]


def test_accepted_sync_counts_and_redirects_every_user(run):
    new, old, same = _user("new"), _user("old"), _user("same")
    osw = FakeOsw()
    report, redirects = run(
        osw,
        [_resolved(new, "create"), _resolved(old, "update"), _resolved(same, "skip")],
    )
    assert report.accepted is True
    assert report.created == [new.full_page_title]
    assert report.updated == [old.full_page_title]
    assert report.skipped == [same.full_page_title]
    assert report.failed == {}
    assert sorted(redirects) == sorted([
        new.full_page_title,
        old.full_page_title,
        same.full_page_title,
    ])
    param_entities = osw.stored_payloads["user-sync"]
    assert [e.title for e in param_entities] == [
        new.full_page_title,
        old.full_page_title,
    ]


def test_prune_skips_an_update_that_was_not_stored(run, monkeypatch):
    ok, bad = _user("ok"), _user("bad")
    cleared = []
    monkeypatch.setattr(
        sync, "clear_jsondata_keys", lambda o, t, k: cleared.append(t) or True
    )
    resolved = []
    for user in (ok, bad):
        r = _resolved(user, "update")
        r.change.diffs = [FieldDiff("websites", ["x"], [], REMOVE)]
        r.apply_fields = {"websites"}
        resolved.append(r)
    osw = FakeOsw({
        "user-sync": lambda titles: _partial_error(
            stored=[ok.full_page_title], failed=[bad.full_page_title]
        )
    })
    report, _ = run(osw, resolved, prune=True)
    assert cleared == [ok.full_page_title]
    assert report.pruned == [ok.full_page_title]


def test_failed_organization_keeps_a_link_the_existing_item_has(run):
    kept, new = _org("Kept"), _org("New")
    user = _user("old", organizations=[kept.full_page_title, new.full_page_title])
    resolved = _resolved(user, "update")
    resolved.change.existing = SimpleNamespace(
        username="old", __iris__={"organization": [kept.full_page_title]}
    )
    osw = FakeOsw({"user-sync: orgs": RuntimeError("down")})
    run(
        osw,
        [resolved],
        org_map={kept.uuid: kept, new.uuid: new},
        link_organizations=True,
    )
    (stored,) = osw.stored_payloads["user-sync"]
    assert stored.organization == [kept.full_page_title]
