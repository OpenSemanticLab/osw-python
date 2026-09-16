"""Unit tests for mapping sources to proposed User/Organization items."""

import uuid

from osw.tools.user_sync import mapping
from osw.tools.user_sync.mapping import (
    ProposedUser,
    map_organization,
    map_user,
    normalize_org_name,
    organization_uuid,
    user_uuid,
)
from osw.tools.user_sync.sources import MwUser, OrcidAffiliation, OrcidProfile

ORCID = "0000-0002-6374-9831"


def _profile(**kw):
    base = dict(orcid_id=ORCID, given_names="Lukas", family_name="Koschmieder")
    base.update(kw)
    return OrcidProfile(**base)


def test_map_orcid_user_full_profile():
    mw = MwUser(name=ORCID)
    profile = _profile(
        emails=["l@example.org"],
        urls=["https://example.org"],
        affiliations=[OrcidAffiliation(organization="Example University")],
    )
    proposed, orgs = map_user(mw, profile)
    assert isinstance(proposed, ProposedUser)
    assert proposed.username == ORCID
    assert proposed.orcid == f"https://orcid.org/{ORCID}"
    assert proposed.first_name == "Lukas"
    assert proposed.surname == "Koschmieder"
    assert proposed.label == "Lukas Koschmieder"
    assert proposed.emails == ["l@example.org"]
    assert proposed.websites == ["https://example.org"]
    assert proposed.placeholder_name is False
    assert len(orgs) == 1
    assert proposed.organizations == [orgs[0].full_page_title]
    assert proposed.full_page_title.startswith("Item:OSW")


def test_map_orcid_user_without_profile_uses_placeholder_names():
    mw = MwUser(name=ORCID)
    proposed, orgs = map_user(mw, None)
    assert proposed.orcid == f"https://orcid.org/{ORCID}"
    assert proposed.first_name == ORCID
    assert proposed.surname == ORCID
    assert proposed.placeholder_name is True
    assert orgs == []


def test_map_non_orcid_user():
    mw = MwUser(name="Alice")
    proposed, _orgs = map_user(mw, None)
    assert proposed.orcid is None
    assert proposed.placeholder_name is True
    assert proposed.uuid == uuid.uuid5(mapping.USER_NAMESPACE, "Alice")


def test_user_uuid_is_deterministic_and_orcid_keyed():
    mw = MwUser(name=ORCID)
    expected = uuid.uuid5(mapping.USER_NAMESPACE, ORCID)
    assert user_uuid(mw) == expected
    assert user_uuid(mw) == user_uuid(MwUser(name=ORCID))


def test_credit_name_split_when_no_given_family():
    mw = MwUser(name=ORCID)
    profile = OrcidProfile(
        orcid_id=ORCID, given_names=None, family_name=None, credit_name="Jane A. Doe"
    )
    proposed, _ = map_user(mw, profile)
    assert proposed.first_name == "Jane"
    assert proposed.surname == "Doe"
    assert proposed.label == "Jane A. Doe"
    assert proposed.placeholder_name is False


def test_organization_uuid_prefers_ror_over_name():
    ror = OrcidAffiliation(organization="Example U", ror_id="https://ror.org/01")
    named = OrcidAffiliation(organization="Example U")
    assert organization_uuid(ror) != organization_uuid(named)
    assert organization_uuid(named) == uuid.uuid5(
        mapping.ORGANIZATION_NAMESPACE, normalize_org_name("Example U")
    )
    assert map_organization(ror).ror_id == "https://ror.org/01"


def test_duplicate_affiliations_deduped():
    mw = MwUser(name=ORCID)
    profile = _profile(
        affiliations=[
            OrcidAffiliation(organization="Example University"),
            OrcidAffiliation(organization="example   university"),
        ]
    )
    proposed, orgs = map_user(mw, profile)
    assert len(orgs) == 1
    assert len(proposed.organizations) == 1


def test_link_organizations_disabled():
    mw = MwUser(name=ORCID)
    profile = _profile(affiliations=[OrcidAffiliation(organization="Example U")])
    proposed, orgs = map_user(mw, profile, link_organizations=False)
    assert orgs == []
    assert proposed.organizations == []
