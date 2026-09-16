"""Build pydantic User/Organization entities from proposals.

Must run within an open OSW connection (the models resolve linked entities on
construction). Organization references are passed as a list of page-title IRIs,
which oold stores in the entity's ``__iris__`` map; the reference attribute is
never read back here, as that would trigger a network resolve.
"""

from __future__ import annotations

from typing import Any, List, Set

from opensemantic.base.v1 import Organization, User

from .mapping import ProposedOrganization, ProposedUser

# The concrete DisplayName type used by the label field.
_DISPLAY_NAME = User.__fields__["label"].type_


def _labels(text: str) -> List[Any]:
    return [_DISPLAY_NAME(text=text)]


def build_organization(proposed: ProposedOrganization) -> Organization:
    return Organization(uuid=proposed.uuid, label=_labels(proposed.name))


def build_user(proposed: ProposedUser) -> User:
    """Build a full User entity for creation."""
    args: dict = {
        "uuid": proposed.uuid,
        "username": proposed.username,
        "first_name": proposed.first_name,
        "surname": proposed.surname,
        "label": _labels(proposed.label),
    }
    if proposed.orcid:
        args["orcid"] = proposed.orcid
    if proposed.emails:
        args["email"] = set(proposed.emails)
    if proposed.websites:
        args["website"] = set(proposed.websites)
    if proposed.organizations:
        args["organization"] = list(proposed.organizations)
    return User(**args)


def apply_update(entity: Any, proposed: ProposedUser, apply_fields: Set[str]) -> Any:
    """Apply the accepted fields onto a loaded existing entity, in place."""
    if "label" in apply_fields:
        entity.label = _labels(proposed.label)
    if "first_name" in apply_fields:
        entity.first_name = proposed.first_name
    if "surname" in apply_fields:
        entity.surname = proposed.surname
    if "orcid" in apply_fields:
        entity.orcid = proposed.orcid
    if "emails" in apply_fields:
        entity.email = set(proposed.emails)
    if "websites" in apply_fields:
        entity.website = set(proposed.websites)
    if "organizations" in apply_fields:
        entity.__iris__["organization"] = list(proposed.organizations)
    return entity
