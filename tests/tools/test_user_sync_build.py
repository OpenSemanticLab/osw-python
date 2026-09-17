"""Unit tests for entity building/updating helpers (fakes; no live models)."""

import uuid
from types import SimpleNamespace

from osw.tools.user_sync.build import _strip_protected, apply_update
from osw.tools.user_sync.mapping import ProposedUser


def _proposed(**kw):
    base = dict(
        uuid=uuid.uuid4(),
        username="u",
        first_name="F",
        surname="S",
        label="F S",
        orcid=None,
        emails=[],
        websites=[],
        organizations=[],
    )
    base.update(kw)
    return ProposedUser(**base)


def _entity():
    return SimpleNamespace(
        label=[],
        first_name="",
        surname="",
        orcid=None,
        email=set(),
        website=set(),
        __iris__={
            "organization": ["Item:OSWa"],
            "employment_contract_status": "Item:OSWx",
        },
    )


def test_strip_protected_removes_only_protected():
    entity = _entity()
    _strip_protected(entity)
    assert "employment_contract_status" not in entity.__iris__
    assert "organization" in entity.__iris__


def test_apply_update_strips_protected_when_in_fields():
    entity = _entity()
    apply_update(entity, _proposed(), {"employment_contract_status"})
    assert "employment_contract_status" not in entity.__iris__


def test_apply_update_keeps_protected_when_not_in_fields():
    entity = _entity()
    apply_update(entity, _proposed(surname="New"), {"surname"})
    assert "employment_contract_status" in entity.__iris__
    assert entity.surname == "New"


def test_apply_update_clears_organization_when_empty():
    entity = _entity()
    apply_update(entity, _proposed(organizations=[]), {"organizations"})
    assert "organization" not in entity.__iris__


def test_apply_update_sets_organization_when_present():
    entity = _entity()
    apply_update(entity, _proposed(organizations=["Item:OSWb"]), {"organizations"})
    assert entity.__iris__["organization"] == ["Item:OSWb"]


def test_apply_update_clears_website():
    entity = _entity()
    entity.website = {"https://x"}
    apply_update(entity, _proposed(websites=[]), {"websites"})
    assert entity.website == set()
