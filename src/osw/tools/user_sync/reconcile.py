"""Reconcile proposed User items against the ones already stored.

Pure logic: given proposed users and an index of existing items, classify each
into NEW, GAP_FILL, CONFLICT or UNCHANGED and record the per-field differences.
The interactive layer consumes this plan; nothing here does IO.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .existing import ExistingUsers
from .mapping import ProposedUser

NEW = "new"
GAP_FILL = "gap_fill"
CONFLICT = "conflict"
UNCHANGED = "unchanged"

# username is the match key and is never reconciled as a value.
SCALAR_FIELDS = ("label", "first_name", "surname", "orcid")
SET_FIELDS = ("emails", "websites", "organizations")
URL_FIELDS = ("orcid", "websites")
RECONCILED_FIELDS = SCALAR_FIELDS + SET_FIELDS


def _is_empty(value: Any) -> bool:
    if value is None or value == "":
        return True
    return isinstance(value, (list, set, tuple)) and len(value) == 0


def _norm_url(value: Any) -> Optional[str]:
    return None if value is None else str(value).rstrip("/")


def _norm_scalar(name: str, value: Any) -> Optional[str]:
    if value is None:
        return None
    return _norm_url(value) if name in URL_FIELDS else str(value)


def _norm_set(name: str, value: Any) -> set:
    if not value:
        return set()
    if name in URL_FIELDS:
        return {_norm_url(x) for x in value}
    return {str(x) for x in value}


def _existing_label(entity: Any) -> Optional[str]:
    for label in getattr(entity, "label", None) or []:
        text = getattr(label, "text", None)
        if text:
            return text
    return None


def existing_fields(entity: Any) -> Dict[str, Any]:
    """Normalized comparable field view of a loaded User entity."""
    return {
        "label": _existing_label(entity),
        "first_name": getattr(entity, "first_name", None),
        "surname": getattr(entity, "surname", None),
        "orcid": _norm_scalar("orcid", getattr(entity, "orcid", None)),
        "emails": _norm_set("emails", getattr(entity, "email", None)),
        "websites": _norm_set("websites", getattr(entity, "website", None)),
        "organizations": _norm_set(
            "organizations", getattr(entity, "organization", None)
        ),
    }


def proposed_fields(proposed: ProposedUser) -> Dict[str, Any]:
    """Normalized comparable field view of a proposed user."""
    return {
        "label": proposed.label,
        "first_name": proposed.first_name,
        "surname": proposed.surname,
        "orcid": _norm_scalar("orcid", proposed.orcid),
        "emails": _norm_set("emails", proposed.emails),
        "websites": _norm_set("websites", proposed.websites),
        "organizations": _norm_set("organizations", proposed.organizations),
    }


@dataclass
class FieldDiff:
    """A single field that would change on an existing item."""

    name: str
    existing: Any
    proposed: Any
    status: str  # GAP_FILL or CONFLICT


@dataclass
class UserChange:
    """The reconciliation outcome for one proposed user."""

    proposed: ProposedUser
    existing: Optional[Any]
    category: str
    diffs: List[FieldDiff] = field(default_factory=list)


def _compare(existing_val: Any, proposed_val: Any) -> Optional[str]:
    """Per-field status, or None when there is nothing to propose."""
    if _is_empty(proposed_val):
        return None
    if _is_empty(existing_val):
        return GAP_FILL
    return UNCHANGED if existing_val == proposed_val else CONFLICT


def reconcile_user(proposed: ProposedUser, existing: Optional[Any]) -> UserChange:
    if existing is None:
        return UserChange(proposed=proposed, existing=None, category=NEW)
    ef = existing_fields(existing)
    pf = proposed_fields(proposed)
    diffs: List[FieldDiff] = []
    has_conflict = has_gap = False
    for name in RECONCILED_FIELDS:
        status = _compare(ef[name], pf[name])
        if status in (GAP_FILL, CONFLICT):
            diffs.append(FieldDiff(name, ef[name], pf[name], status))
            has_conflict = has_conflict or status == CONFLICT
            has_gap = has_gap or status == GAP_FILL
    category = CONFLICT if has_conflict else GAP_FILL if has_gap else UNCHANGED
    return UserChange(
        proposed=proposed, existing=existing, category=category, diffs=diffs
    )


@dataclass
class ReconcilePlan:
    """All per-user reconciliation outcomes for a run."""

    changes: List[UserChange] = field(default_factory=list)

    def by_category(self, category: str) -> List[UserChange]:
        return [c for c in self.changes if c.category == category]

    @property
    def conflicts(self) -> List[UserChange]:
        return self.by_category(CONFLICT)

    def counts(self) -> Dict[str, int]:
        counter = Counter(c.category for c in self.changes)
        return {
            cat: counter.get(cat, 0) for cat in (NEW, GAP_FILL, CONFLICT, UNCHANGED)
        }


def reconcile(
    proposed_users: List[ProposedUser], existing: ExistingUsers
) -> ReconcilePlan:
    changes = [reconcile_user(p, existing.get(p.username)) for p in proposed_users]
    return ReconcilePlan(changes=changes)
