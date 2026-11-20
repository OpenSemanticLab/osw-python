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
        website={"https://x"},
        organization=["Item:OSWa"],
        employment_contract_status="Item:OSWx",
    )


def test_strip_protected_unsets_only_protected():
    entity = _entity()
    _strip_protected(entity)
    assert entity.employment_contract_status is None
    assert entity.organization == ["Item:OSWa"]


def test_apply_update_strips_protected_when_in_fields():
    entity = _entity()
    apply_update(entity, _proposed(), {"employment_contract_status"})
    assert entity.employment_contract_status is None


def test_apply_update_strips_protected_when_not_in_fields():
    entity = _entity()
    apply_update(entity, _proposed(surname="New"), {"surname"})
    assert entity.employment_contract_status is None
    assert entity.surname == "New"


def test_apply_update_unsets_organization_when_empty():
    entity = _entity()
    apply_update(entity, _proposed(organizations=[]), {"organizations"})
    assert entity.organization is None


def test_apply_update_sets_organization_when_present():
    entity = _entity()
    apply_update(entity, _proposed(organizations=["Item:OSWb"]), {"organizations"})
    assert entity.organization == ["Item:OSWb"]


def test_apply_update_unsets_website_when_empty():
    entity = _entity()
    apply_update(entity, _proposed(websites=[]), {"websites"})
    assert entity.website is None


def test_apply_update_sets_website_when_present():
    entity = _entity()
    apply_update(entity, _proposed(websites=["https://y"]), {"websites"})
    assert entity.website == {"https://y"}


def test_apply_update_sets_username_when_accepted():
    entity = _entity()
    entity.username = None
    apply_update(entity, _proposed(username="u"), {"username"})
    assert entity.username == "u"
