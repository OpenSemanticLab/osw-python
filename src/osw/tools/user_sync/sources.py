"""External data sources for the user-item sync tool.

This module wraps the MediaWiki ``allusers`` API. The ORCID public-API client is
added in a later phase.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence

# An ORCID iD is 16 digits in groups of four; the last character may be an X.
ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")

_ALLUSERS_PROPS = "registration|editcount|groups|centralids|blockinfo"


def is_orcid_username(name: str) -> bool:
    """True if a MediaWiki username is an ORCID iD (whitelisted ORCID login)."""
    return bool(ORCID_RE.match(name or ""))


@dataclass
class MwUser:
    """A MediaWiki account and the metadata exposed by the ``allusers`` API."""

    name: str
    userid: Optional[int] = None
    registration: Optional[str] = None
    editcount: int = 0
    groups: List[str] = field(default_factory=list)
    blocked: bool = False

    @property
    def is_orcid(self) -> bool:
        return is_orcid_username(self.name)

    @property
    def orcid_id(self) -> Optional[str]:
        """The bare ORCID iD when the username is one, else None."""
        return self.name if self.is_orcid else None

    @classmethod
    def from_api(cls, raw: Dict[str, Any]) -> MwUser:
        return cls(
            name=raw["name"],
            userid=raw.get("userid"),
            registration=raw.get("registration") or None,
            editcount=int(raw.get("editcount") or 0),
            groups=list(raw.get("groups") or []),
            blocked="blockid" in raw,
        )


def _iter_allusers(site: Any, batch: Any = "max") -> Iterator[Dict[str, Any]]:
    """Yield raw ``allusers`` records, following API continuation."""
    params: Dict[str, Any] = {
        "list": "allusers",
        "auprop": _ALLUSERS_PROPS,
        "aulimit": batch,
    }
    while True:
        resp = site.api("query", **params)
        yield from resp.get("query", {}).get("allusers", [])
        cont = resp.get("continue")
        if not cont:
            break
        params.update(cont)


def enumerate_mw_users(
    site: Any,
    excluded_groups: Sequence[str] = ("bot",),
    include_non_orcid: bool = True,
    limit: Optional[int] = None,
    batch: Any = "max",
) -> List[MwUser]:
    """List MediaWiki accounts to sync.

    Args:
        site: An object exposing ``api("query", ...)`` (an mwclient Site).
        excluded_groups: Accounts in any of these groups are skipped (bots).
        include_non_orcid: If False, keep only ORCID-username accounts.
        limit: Keep at most this many accounts after filtering.
        batch: ``aulimit`` value passed to the API.
    """
    excluded = set(excluded_groups)
    users: List[MwUser] = []
    for raw in _iter_allusers(site, batch=batch):
        user = MwUser.from_api(raw)
        if excluded.intersection(user.groups):
            continue
        if not include_non_orcid and not user.is_orcid:
            continue
        users.append(user)
        if limit is not None and len(users) >= limit:
            break
    return users


def partition_by_orcid(users: Iterable[MwUser]) -> Dict[str, List[MwUser]]:
    """Split users into ``{"orcid": [...], "other": [...]}``."""
    orcid: List[MwUser] = []
    other: List[MwUser] = []
    for user in users:
        (orcid if user.is_orcid else other).append(user)
    return {"orcid": orcid, "other": other}
