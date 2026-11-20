"""Unit tests for the ORCID public-API client."""

import pytest
import requests

from osw.tools.user_sync import sources
from osw.tools.user_sync.sources import (
    OrcidProfile,
    OrcidRateLimitError,
    fetch_orcid_record,
    parse_orcid_record,
)

ORCID_ID = "0000-0002-1825-0097"

RECORD = {
    "person": {
        "name": {
            "given-names": {"value": "Jane"},
            "family-name": {"value": "Doe"},
            "credit-name": {"value": "Jane A. Doe"},
        },
        "other-names": {"other-name": [{"content": "J. Doe"}]},
        "emails": {"email": [{"email": "jane@example.org"}]},
        "researcher-urls": {
            "researcher-url": [{"url": {"value": "https://jane.example.org"}}]
        },
    },
    "activities-summary": {
        "employments": {
            "affiliation-group": [
                {
                    "summaries": [
                        {
                            "employment-summary": {
                                "department-name": "Physics",
                                "role-title": "Researcher",
                                "organization": {
                                    "name": "Example University",
                                    "disambiguated-organization": {
                                        "disambiguated-organization-identifier": (
                                            "https://ror.org/01abc2345"
                                        ),
                                        "disambiguation-source": "ROR",
                                    },
                                },
                            }
                        }
                    ]
                }
            ]
        }
    },
}


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None):
        self.status_code = status_code
        self._json = json_data
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, headers=None, timeout=None):
        self.calls += 1
        return self._responses.pop(0)


def test_parse_record_full():
    p = parse_orcid_record(RECORD, ORCID_ID)
    assert p.given_names == "Jane"
    assert p.family_name == "Doe"
    assert p.credit_name == "Jane A. Doe"
    assert p.display_name == "Jane A. Doe"
    assert p.other_names == ["J. Doe"]
    assert p.emails == ["jane@example.org"]
    assert p.urls == ["https://jane.example.org"]
    assert p.orcid_uri == f"https://orcid.org/{ORCID_ID}"
    assert len(p.affiliations) == 1
    aff = p.affiliations[0]
    assert aff.organization == "Example University"
    assert aff.ror_id == "https://ror.org/01abc2345"
    assert aff.department == "Physics"
    assert aff.role == "Researcher"


def test_parse_record_sparse():
    p = parse_orcid_record({"person": {}}, ORCID_ID)
    assert p.given_names is None
    assert p.display_name is None
    assert p.emails == []
    assert p.affiliations == []


def test_display_name_falls_back_to_given_family():
    p = OrcidProfile(orcid_id=ORCID_ID, given_names="Jane", family_name="Doe")
    assert p.display_name == "Jane Doe"


def test_fetch_404_returns_none():
    session = FakeSession([FakeResponse(status_code=404)])
    assert fetch_orcid_record(ORCID_ID, session=session) is None


def test_fetch_200_parses():
    session = FakeSession([FakeResponse(status_code=200, json_data=RECORD)])
    p = fetch_orcid_record(ORCID_ID, session=session)
    assert p.family_name == "Doe"


def test_fetch_retries_on_429(monkeypatch):
    monkeypatch.setattr(sources.time, "sleep", lambda *_: None)
    session = FakeSession([
        FakeResponse(status_code=429, headers={"Retry-After": "0"}),
        FakeResponse(status_code=200, json_data=RECORD),
    ])
    p = fetch_orcid_record(ORCID_ID, session=session)
    assert p.given_names == "Jane"
    assert session.calls == 2


def test_fetch_raises_when_rate_limited(monkeypatch):
    monkeypatch.setattr(sources.time, "sleep", lambda *_: None)
    session = FakeSession([FakeResponse(status_code=429) for _ in range(3)])
    with pytest.raises(OrcidRateLimitError):
        fetch_orcid_record(ORCID_ID, session=session, max_retries=2)


def test_fetch_uses_cache():
    session = FakeSession([FakeResponse(status_code=200, json_data=RECORD)])
    cache = {}
    first = fetch_orcid_record(ORCID_ID, session=session, cache=cache)
    second = fetch_orcid_record(ORCID_ID, session=session, cache=cache)
    assert first is second
    assert session.calls == 1
