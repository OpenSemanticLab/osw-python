"""Map MediaWiki accounts and ORCID profiles to proposed OSW items.

These functions are pure: they compute the field values and deterministic ids of
the items to store, without instantiating the pydantic models (which requires an
open OSW connection) or touching the network. The store step builds the actual
``User`` / ``Organization`` entities from these proposals.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from osw.data.import_utility import uuid_to_full_page_title

from .config import ORGANIZATION_CATEGORY, USER_CATEGORY
from .sources import MwUser, OrcidAffiliation, OrcidProfile


def _category_namespace(category: str) -> uuid.UUID:
    """Derive the uuid5 namespace of a category from its page title."""
    return uuid.UUID(category.split("OSW")[-1])


USER_NAMESPACE = _category_namespace(USER_CATEGORY)
ORGANIZATION_NAMESPACE = _category_namespace(ORGANIZATION_CATEGORY)


@dataclass
class ProposedOrganization:
    """An Organization item derived from an ORCID affiliation."""

    uuid: uuid.UUID
    name: str
    ror_id: Optional[str] = None

    @property
    def full_page_title(self) -> str:
        return uuid_to_full_page_title(self.uuid)


@dataclass
class ProposedUser:
    """A User item derived from a MediaWiki account and optional ORCID data."""

    uuid: uuid.UUID
    username: str
    first_name: str
    surname: str
    label: str
    orcid: Optional[str] = None
    emails: List[str] = field(default_factory=list)
    websites: List[str] = field(default_factory=list)
    organizations: List[str] = field(default_factory=list)
    placeholder_name: bool = False

    @property
    def full_page_title(self) -> str:
        return uuid_to_full_page_title(self.uuid)


def normalize_org_name(name: str) -> str:
    """Collapse whitespace and lowercase, for a stable org identity key."""
    return " ".join(name.lower().split())


def user_uuid(mw_user: MwUser) -> uuid.UUID:
    """Deterministic uuid5: keyed on ORCID iD for ORCID users, else username."""
    key = mw_user.orcid_id or mw_user.name
    return uuid.uuid5(USER_NAMESPACE, key)


def organization_uuid(affiliation: OrcidAffiliation) -> uuid.UUID:
    """Deterministic uuid5: keyed on ROR id when present, else the org name."""
    key = affiliation.ror_id or normalize_org_name(affiliation.organization)
    return uuid.uuid5(ORGANIZATION_NAMESPACE, key)


def map_organization(affiliation: OrcidAffiliation) -> ProposedOrganization:
    return ProposedOrganization(
        uuid=organization_uuid(affiliation),
        name=affiliation.organization,
        ror_id=affiliation.ror_id,
    )


def _derive_names(
    profile: Optional[OrcidProfile], username: str
) -> Tuple[str, str, str, bool]:
    """Return (first_name, surname, label, is_placeholder).

    Prefers ORCID given/family names, then a split of the display name, then a
    username-based placeholder when no name information is available.
    """
    given = profile.given_names if profile else None
    family = profile.family_name if profile else None
    display = profile.display_name if profile else None
    if given and family:
        return given, family, display or f"{given} {family}", False
    if display:
        parts = display.split()
        first = given or parts[0]
        surname = family or (parts[-1] if len(parts) > 1 else parts[0])
        return first, surname, display, False
    if given or family:
        first = given or family
        surname = family or given
        return first, surname, f"{first} {surname}", False
    return username, username, username, True


def map_user(
    mw_user: MwUser,
    profile: Optional[OrcidProfile] = None,
    include_websites: bool = False,
    link_organizations: bool = False,
) -> Tuple[ProposedUser, List[ProposedOrganization]]:
    """Build a ProposedUser (and any linked organizations) from the sources.

    Email and names are always taken from the profile (core). Websites and
    organizations are populated only when their flag is enabled.
    """
    orcid_uri = f"https://orcid.org/{mw_user.orcid_id}" if mw_user.orcid_id else None
    first, surname, label, placeholder = _derive_names(profile, mw_user.name)

    organizations: List[ProposedOrganization] = []
    org_titles: List[str] = []
    if link_organizations and profile:
        seen = set()
        for affiliation in profile.affiliations:
            org = map_organization(affiliation)
            if org.uuid in seen:
                continue
            seen.add(org.uuid)
            organizations.append(org)
            org_titles.append(org.full_page_title)

    proposed = ProposedUser(
        uuid=user_uuid(mw_user),
        username=mw_user.name,
        first_name=first,
        surname=surname,
        label=label,
        orcid=orcid_uri,
        emails=list(profile.emails) if profile else [],
        websites=list(profile.urls) if (profile and include_websites) else [],
        organizations=org_titles,
        placeholder_name=placeholder,
    )
    return proposed, organizations
