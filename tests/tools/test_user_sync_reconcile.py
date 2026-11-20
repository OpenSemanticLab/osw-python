"""Unit tests for the reconciliation engine."""

import uuid
from types import SimpleNamespace

from osw.tools.user_sync.existing import ExistingUsers
from osw.tools.user_sync.mapping import ProposedUser
from osw.tools.user_sync.reconcile import (
    CONFLICT,
    GAP_FILL,
    NEW,
    REMOVE,
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
        username=ORCID,
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
        username=base["username"],
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
        enabled_fields=frozenset({"organizations"}),
    )
    assert change.category == UNCHANGED


def test_disabled_optional_field_removed_when_pruning():
    # organizations disabled + existing value + prune -> REMOVE
    change = reconcile_user(
        _proposed(), _entity(organization=["Item:OSWa"]), prune=True
    )
    assert change.category == GAP_FILL
    removes = [d for d in change.diffs if d.status == REMOVE]
    assert [d.name for d in removes] == ["organizations"]
    assert removes[0].proposed is None


def test_prune_off_keeps_disabled_and_protected():
    entity = _entity()
    entity.__iris__ = {
        "organization": ["Item:OSWa"],
        "employment_contract_status": "Item:OSWx",
    }
    change = reconcile_user(_proposed(), entity)  # prune off (default)
    assert change.category == UNCHANGED
    assert change.diffs == []


def test_enabled_optional_field_not_removed():
    change = reconcile_user(
        _proposed(organizations=["Item:OSWa"]),
        _entity(organization=["Item:OSWa"]),
        enabled_fields=frozenset({"organizations"}),
    )
    assert change.category == UNCHANGED


def test_protected_field_removed_when_pruning():
    entity = _entity()
    entity.__iris__ = {"employment_contract_status": "Item:OSWx"}
    change = reconcile_user(_proposed(), entity, prune=True)
    removes = [d.name for d in change.diffs if d.status == REMOVE]
    assert "employment_contract_status" in removes
    assert change.category == GAP_FILL


def test_protected_default_not_stored_is_not_removed():
    # The loaded entity shows the model default IRI, the stored page has none.
    entity = _entity()
    entity.__iris__ = {"employment_contract_status": "Item:OSWdefault"}
    change = reconcile_user(
        _proposed(), entity, prune=True, stored_jsondata={"username": ORCID}
    )
    assert [d for d in change.diffs if d.status == REMOVE] == []
    assert change.category == UNCHANGED


def test_protected_field_stored_is_removed_when_pruning():
    entity = _entity()
    entity.__iris__ = {"employment_contract_status": "Item:OSWx"}
    change = reconcile_user(
        _proposed(),
        entity,
        prune=True,
        stored_jsondata={"employment_contract_status": "Item:OSWx"},
    )
    removes = [d.name for d in change.diffs if d.status == REMOVE]
    assert removes == ["employment_contract_status"]


def test_reconcile_uses_the_stored_jsondata_of_the_index():
    entity = _entity()
    entity.__iris__ = {"employment_contract_status": "Item:OSWdefault"}
    existing = ExistingUsers(
        by_username={ORCID: entity}, stored_jsondata={ORCID: {"username": ORCID}}
    )
    plan = reconcile([_proposed()], existing, prune=True)
    assert plan.changes[0].category == UNCHANGED


def test_missing_label_is_gap_fill():
    change = reconcile_user(_proposed(label="Lukas Koschmieder"), _entity(label=None))
    assert change.category == GAP_FILL
    assert change.diffs[0].name == "label"


class _OrgTrap:
    """A loaded-entity stand-in whose organization attribute must never be read."""

    __iris__ = {"organization": ["Item:OSWa", "Item:OSWb"]}
    label = [SimpleNamespace(text="X Y")]
    first_name = "X"
    surname = "Y"
    orcid = None
    email: set = set()
    website: set = set()

    @property
    def organization(self):
        raise RuntimeError("relation must not be resolved during reconcile")


def test_existing_orgs_read_from_iris_without_resolving():
    from osw.tools.user_sync.reconcile import existing_fields

    ef = existing_fields(_OrgTrap())
    assert ef["organizations"] == {"Item:OSWa", "Item:OSWb"}


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


def test_placeholder_name_is_not_compared_for_an_existing_item():
    proposed = _proposed(
        first_name="bob", surname="bob", label="bob", placeholder_name=True
    )
    for existing in (
        _entity(label="Robert Smith", first_name="Robert", surname="Smith"),
        _entity(label=None, first_name=None, surname=None),
    ):
        change = reconcile_user(proposed, existing)
        names = {d.name for d in change.diffs}
        assert not names & {"label", "first_name", "surname"}
        assert change.category == UNCHANGED


def test_placeholder_name_is_kept_for_a_new_item():
    change = reconcile_user(_proposed(placeholder_name=True), None)
    assert change.category == NEW


def test_missing_username_is_filled_on_an_existing_item():
    # An item found by its page title instead of its username has none yet.
    change = reconcile_user(_proposed(), _entity(username=None))
    assert change.category == GAP_FILL
    assert [(d.name, d.proposed) for d in change.diffs] == [("username", ORCID)]


def test_placeholder_user_without_username_still_gets_it():
    change = reconcile_user(
        _proposed(placeholder_name=True, label=ORCID), _entity(username=None)
    )
    assert change.category == GAP_FILL
    assert [d.name for d in change.diffs] == ["username"]


def test_protected_field_stored_as_empty_list_is_removed_when_pruning():
    # [] is not a valid value for the single-valued field, so it is removed.
    entity = _entity()
    entity.__iris__ = {"employment_contract_status": "Item:OSWdefault"}
    change = reconcile_user(
        _proposed(),
        entity,
        prune=True,
        stored_jsondata={"username": ORCID, "employment_contract_status": []},
    )
    assert [(d.name, d.status) for d in change.diffs] == [
        ("employment_contract_status", REMOVE)
    ]
