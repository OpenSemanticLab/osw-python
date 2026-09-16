"""Unit tests for the reconciliation engine."""

import uuid
from types import SimpleNamespace

from osw.tools.user_sync.existing import ExistingUsers
from osw.tools.user_sync.mapping import ProposedUser
from osw.tools.user_sync.reconcile import (
    CONFLICT,
    GAP_FILL,
    NEW,
    UNCHANGED,
    reconcile,
    reconcile_user,
)

ORCID = "0000-0002-6374-9831"


def _proposed(**kw):
    base = dict(
        uuid=uuid.uuid4(),
        username=ORCID,
        first_name="Lukas",
        surname="Koschmieder",
        label="Lukas Koschmieder",
        orcid=f"https://orcid.org/{ORCID}",
        emails=[],
        websites=[],
        organizations=[],
    )
    base.update(kw)
    return ProposedUser(**base)


def _entity(**kw):
    base = dict(
        label="Lukas Koschmieder",
        first_name="Lukas",
        surname="Koschmieder",
        orcid=f"https://orcid.org/{ORCID}",
        email=None,
        website=None,
        organization=None,
    )
    base.update(kw)
    return SimpleNamespace(
        label=[SimpleNamespace(text=base["label"])] if base["label"] else [],
        first_name=base["first_name"],
        surname=base["surname"],
        orcid=base["orcid"],
        email=set(base["email"] or []),
        website=set(base["website"] or []),
        organization=set(base["organization"] or []),
    )


def test_new_when_no_existing():
    change = reconcile_user(_proposed(), None)
    assert change.category == NEW
    assert change.diffs == []


def test_unchanged_when_equal():
    change = reconcile_user(_proposed(), _entity())
    assert change.category == UNCHANGED
    assert change.diffs == []


def test_gap_fill_for_missing_field():
    proposed = _proposed(emails=["l@example.org"])
    change = reconcile_user(proposed, _entity(email=None))
    assert change.category == GAP_FILL
    assert [d.name for d in change.diffs] == ["emails"]
    assert change.diffs[0].status == GAP_FILL


def test_conflict_on_differing_value():
    change = reconcile_user(_proposed(surname="Koschmieder"), _entity(surname="Kosch"))
    assert change.category == CONFLICT
    assert change.diffs[0].name == "surname"
    assert change.diffs[0].existing == "Kosch"
    assert change.diffs[0].proposed == "Koschmieder"


def test_conflict_dominates_gap_fill():
    proposed = _proposed(surname="Koschmieder", emails=["l@example.org"])
    change = reconcile_user(proposed, _entity(surname="Kosch", email=None))
    assert change.category == CONFLICT
    names = {d.name for d in change.diffs}
    assert names == {"surname", "emails"}


def test_empty_proposal_does_not_clear_existing():
    change = reconcile_user(_proposed(emails=[]), _entity(email=["keep@example.org"]))
    assert change.category == UNCHANGED
    assert change.diffs == []


def test_orcid_trailing_slash_not_a_conflict():
    change = reconcile_user(
        _proposed(orcid=f"https://orcid.org/{ORCID}"),
        _entity(orcid=f"https://orcid.org/{ORCID}/"),
    )
    assert change.category == UNCHANGED


def test_set_order_independent():
    change = reconcile_user(
        _proposed(organizations=["Item:OSWb", "Item:OSWa"]),
        _entity(organization=["Item:OSWa", "Item:OSWb"]),
    )
    assert change.category == UNCHANGED


def test_missing_label_is_gap_fill():
    change = reconcile_user(_proposed(label="Lukas Koschmieder"), _entity(label=None))
    assert change.category == GAP_FILL
    assert change.diffs[0].name == "label"


def test_reconcile_plan_counts():
    proposed = [
        _proposed(username="new-user"),
        _proposed(username=ORCID),
        _proposed(username="conflict-user", surname="New"),
    ]
    existing = ExistingUsers(
        by_username={
            ORCID: _entity(),
            "conflict-user": _entity(surname="Old"),
        }
    )
    plan = reconcile(proposed, existing)
    counts = plan.counts()
    assert counts == {NEW: 1, GAP_FILL: 0, CONFLICT: 1, UNCHANGED: 1}
    assert [c.proposed.username for c in plan.conflicts] == ["conflict-user"]
