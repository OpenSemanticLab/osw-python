"""External data sources for the user-item sync tool.

This module wraps the MediaWiki ``allusers`` API. The ORCID public-API client is
added in a later phase.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence

import requests

from .config import ORCID_API_BASE_DEFAULT

# An ORCID iD is 16 digits in groups of four; the last character may be an X.
ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")

_ALLUSERS_PROPS = "registration|editcount|groups|centralids|blockinfo"

# MediaWiki default reserved system usernames. These ship with MediaWiki and are
# the same across instances, so skipping them is not a per-instance skip-list.
RESERVED_USERNAMES = frozenset({
    "MediaWiki default",
    "Maintenance script",
    "Conversion script",
    "Template namespace initialisation script",
    "ScriptImporter",
    "Delete page script",
    "Move page script",
    "Command line script",
    "Unknown user",
    "MediaWiki message delivery",
    "Flow talk page manager",
    "Abuse filter",
    "New user message",
})


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
    excluded_usernames: Sequence[str] = (),
    include_orcid: bool = True,
    include_non_orcid: bool = True,
    limit: Optional[int] = None,
    batch: Any = "max",
) -> List[MwUser]:
    """List MediaWiki accounts to sync.

    Args:
        site: An object exposing ``api("query", ...)`` (an mwclient Site).
        excluded_groups: Accounts in any of these groups are skipped (bots, admins).
        excluded_usernames: Exact usernames to skip (reserved system accounts).
        include_orcid: If False, skip ORCID-username accounts.
        include_non_orcid: If False, keep only ORCID-username accounts.
        limit: Keep at most this many accounts after filtering.
        batch: ``aulimit`` value passed to the API.
    """
    excluded = set(excluded_groups)
    excluded_names = set(excluded_usernames)
    users: List[MwUser] = []
    for raw in _iter_allusers(site, batch=batch):
        user = MwUser.from_api(raw)
        if user.name in excluded_names:
            continue
        if excluded.intersection(user.groups):
            continue
        if not include_non_orcid and not user.is_orcid:
            continue
        if not include_orcid and user.is_orcid:
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


class OrcidRateLimitError(RuntimeError):
    """Raised when the ORCID public API keeps returning HTTP 429."""


@dataclass
class OrcidAffiliation:
    """An employment entry from an ORCID record."""

    organization: str
    ror_id: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None


@dataclass
class OrcidProfile:
    """The subset of a public ORCID record that maps to an OSW User item."""

    orcid_id: str
    given_names: Optional[str] = None
    family_name: Optional[str] = None
    credit_name: Optional[str] = None
    other_names: List[str] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    affiliations: List[OrcidAffiliation] = field(default_factory=list)

    @property
    def orcid_uri(self) -> str:
        return f"https://orcid.org/{self.orcid_id}"

    @property
    def display_name(self) -> Optional[str]:
        """Best full name: credit name, else given + family, else None."""
        if self.credit_name:
            return self.credit_name
        parts = [p for p in (self.given_names, self.family_name) if p]
        return " ".join(parts) or None


def _value(node: Any, *keys: str) -> Optional[Any]:
    """Safely walk nested dicts, returning None on any missing key."""
    cur = node
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _parse_affiliations(activities: Any) -> List[OrcidAffiliation]:
    affiliations: List[OrcidAffiliation] = []
    groups = _value(activities, "employments", "affiliation-group") or []
    for group in groups:
        for summary in group.get("summaries") or []:
            emp = summary.get("employment-summary") or {}
            org = emp.get("organization") or {}
            name = org.get("name")
            if not name:
                continue
            ror = None
            disamb = org.get("disambiguated-organization") or {}
            if (disamb.get("disambiguation-source") or "").upper() == "ROR":
                ror = disamb.get("disambiguated-organization-identifier")
            affiliations.append(
                OrcidAffiliation(
                    organization=name,
                    ror_id=ror,
                    department=emp.get("department-name"),
                    role=emp.get("role-title"),
                )
            )
    return affiliations


def parse_orcid_record(data: Dict[str, Any], orcid_id: str) -> OrcidProfile:
    """Parse an ORCID ``/record`` JSON payload into an OrcidProfile (pure)."""
    person = data.get("person") or {}
    other_names = [
        n.get("content")
        for n in _value(person, "other-names", "other-name") or []
        if n.get("content")
    ]
    emails = [
        e.get("email")
        for e in _value(person, "emails", "email") or []
        if e.get("email")
    ]
    urls = [
        _value(u, "url", "value")
        for u in _value(person, "researcher-urls", "researcher-url") or []
        if _value(u, "url", "value")
    ]
    return OrcidProfile(
        orcid_id=orcid_id,
        given_names=_value(person, "name", "given-names", "value"),
        family_name=_value(person, "name", "family-name", "value"),
        credit_name=_value(person, "name", "credit-name", "value"),
        other_names=other_names,
        emails=emails,
        urls=urls,
        affiliations=_parse_affiliations(data.get("activities-summary") or {}),
    )


def fetch_orcid_record(
    orcid_id: str,
    session: Optional[requests.Session] = None,
    base: str = ORCID_API_BASE_DEFAULT,
    timeout: float = 30.0,
    max_retries: int = 2,
    cache: Optional[Dict[str, Optional[OrcidProfile]]] = None,
) -> Optional[OrcidProfile]:
    """Fetch and parse a public ORCID record.

    Returns None when the record does not exist (HTTP 404). Retries on HTTP 429
    honoring ``Retry-After`` and raises OrcidRateLimitError if still limited.
    """
    if cache is not None and orcid_id in cache:
        return cache[orcid_id]
    sess = session or requests.Session()
    url = f"{base}/{orcid_id}/record"
    headers = {"Accept": "application/json"}
    result: Optional[OrcidProfile] = None
    for attempt in range(max_retries + 1):
        resp = sess.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 404:
            result = None
            break
        if resp.status_code == 429:
            if attempt >= max_retries:
                raise OrcidRateLimitError(f"ORCID rate limit for {orcid_id}")
            time.sleep(float(resp.headers.get("Retry-After", 1)))
            continue
        resp.raise_for_status()
        result = parse_orcid_record(resp.json(), orcid_id)
        break
    if cache is not None:
        cache[orcid_id] = result
    return result
