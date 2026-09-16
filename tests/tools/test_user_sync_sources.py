"""Unit tests for MediaWiki user enumeration and classification."""

from osw.tools.user_sync.sources import (
    MwUser,
    enumerate_mw_users,
    is_orcid_username,
    partition_by_orcid,
)


class FakeSite:
    """Mimics mwclient Site.api for list=allusers, with continuation."""

    def __init__(self, pages):
        self._pages = pages
        self.calls = 0

    def api(self, action, **params):
        assert action == "query"
        assert params["list"] == "allusers"
        page = self._pages[self.calls]
        self.calls += 1
        return page


def _page(users, cont=None):
    resp = {"query": {"allusers": users}}
    if cont is not None:
        resp["continue"] = cont
    return resp


def test_is_orcid_username():
    assert is_orcid_username("0000-0002-6374-9831")
    assert is_orcid_username("0000-0003-0930-082X")
    assert not is_orcid_username("Alice")
    assert not is_orcid_username("")


def test_from_api_classifies_orcid_and_blocked():
    u = MwUser.from_api({
        "name": "0000-0002-6374-9831",
        "userid": 16,
        "registration": "2026-01-21T08:31:14Z",
        "editcount": 37,
        "groups": ["*", "user", "autoconfirmed"],
    })
    assert u.is_orcid is True
    assert u.orcid_id == "0000-0002-6374-9831"
    assert u.editcount == 37
    assert u.blocked is False


def test_enumerate_follows_continuation_and_excludes_bots():
    site = FakeSite([
        _page(
            [
                {"name": "0000-0002-6374-9831", "userid": 16, "groups": ["user"]},
                {"name": "SyncBot", "userid": 2, "groups": ["user", "bot"]},
            ],
            cont={"aufrom": "M"},
        ),
        _page([
            {"name": "Maintainer", "userid": 3, "groups": ["sysop"]},
        ]),
    ])
    users = enumerate_mw_users(site)
    names = [u.name for u in users]
    assert names == ["0000-0002-6374-9831", "Maintainer"]  # bot dropped
    assert site.calls == 2  # continuation followed


def test_enumerate_orcid_only_and_limit():
    site = FakeSite([
        _page([
            {"name": "0000-0002-6374-9831", "groups": ["user"]},
            {"name": "Alice", "groups": ["user"]},
            {"name": "0000-0003-0930-082X", "groups": ["user"]},
        ])
    ])
    orcid_only = enumerate_mw_users(site, include_non_orcid=False)
    assert [u.name for u in orcid_only] == [
        "0000-0002-6374-9831",
        "0000-0003-0930-082X",
    ]

    site2 = FakeSite([
        _page([
            {"name": "0000-0002-6374-9831", "groups": ["user"]},
            {"name": "Alice", "groups": ["user"]},
        ])
    ])
    limited = enumerate_mw_users(site2, limit=1)
    assert len(limited) == 1


def test_partition_by_orcid():
    users = [
        MwUser(name="0000-0002-6374-9831"),
        MwUser(name="Alice"),
    ]
    parts = partition_by_orcid(users)
    assert [u.name for u in parts["orcid"]] == ["0000-0002-6374-9831"]
    assert [u.name for u in parts["other"]] == ["Alice"]
