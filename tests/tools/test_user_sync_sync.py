"""Unit tests for the orchestrator (dry-run path, no live models)."""

from types import SimpleNamespace

from osw.data.import_utility import uuid_to_full_page_title
from osw.tools.user_sync.config import SyncConfig
from osw.tools.user_sync.interactive import Prompter
from osw.tools.user_sync.mapping import user_uuid
from osw.tools.user_sync.sources import MwUser
from osw.tools.user_sync.sync import SyncReport, run_user_sync
from osw.wtsite import WtPage

ORCID = "0000-0002-6374-9831"

ORCID_RECORD = {
    "person": {
        "name": {
            "given-names": {"value": "Lukas"},
            "family-name": {"value": "Koschmieder"},
        }
    }
}


class FakeWtPage(WtPage):
    """A WtPage that serves a fixed jsondata slot without a wiki."""

    def __init__(self, title, jsondata=None):
        self.title = title
        self._jsondata = jsondata or {}

    def get_slot_content(self, slot, *args, **kwargs):
        return self._jsondata


class FakeMwSite:
    def __init__(self, extra_users=()):
        self.extra_users = list(extra_users)

    def api(self, action, **params):
        assert action == "query" and params["list"] == "allusers"
        return {
            "query": {
                "allusers": [
                    {"name": ORCID, "groups": ["user"]},
                    {"name": "SyncBot", "groups": ["user", "bot"]},
                    *self.extra_users,
                ]
            }
        }


class FakeOsw:
    def __init__(self, extra_users=(), existing_pages=None):
        self.mw_site = FakeMwSite(extra_users)
        self.site = SimpleNamespace(
            semantic_search=self._semantic_search, get_page=self._get_page
        )
        self.existing_pages = existing_pages or {}
        self.loaded = []
        self.store_calls = 0

    def _semantic_search(self, query):
        return [SimpleNamespace(titles=[], truncated=False, next_offset=None, count=0)]

    def _get_missing_page_titles(self, titles, confirm_delay_s=5):
        return [t for t in titles if t not in self.existing_pages]

    def _get_page(self, param):
        pages = [FakeWtPage(t) for t in param.titles]
        return SimpleNamespace(pages=pages, errors=[])

    def load_entity(self, param):
        self.loaded.extend(param.titles)
        return [self.existing_pages[t] for t in param.titles]

    def store_entity(self, param):
        self.store_calls += 1


class FakeResponse:
    status_code = 200
    headers: dict = {}

    def json(self):
        return ORCID_RECORD

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self):
        self.calls = 0

    def get(self, url, headers=None, timeout=None):
        self.calls += 1
        return FakeResponse()


class CapturingIO:
    def __init__(self):
        self.outputs = []

    def input(self, prompt=""):  # pragma: no cover - not used in dry-run
        raise AssertionError("dry-run must not prompt")

    def output(self, text=""):
        self.outputs.append(text)


def test_summary_reads_accepted_state():
    assert SyncReport(accepted=False).summary().startswith("no changes written")
    assert SyncReport(accepted=True, created=["x"]).summary().startswith("applied")


def test_dry_run_previews_without_writing():
    osw = FakeOsw()
    io = CapturingIO()
    session = FakeSession()
    report = run_user_sync(
        SyncConfig(domain="d", dry_run=True),
        osw=osw,
        prompter=Prompter(io.input, io.output),
        session=session,
    )
    assert report.accepted is False
    assert osw.store_calls == 0  # nothing written
    assert session.calls == 1  # ORCID user enriched, bot skipped
    joined = "\n".join(io.outputs)
    assert ORCID in joined
    assert "new=1" in joined  # bot excluded, only the ORCID user
    assert report.missing_email == [ORCID]  # record has no email
    assert "no ORCID email" in joined


def test_requires_connection():
    try:
        run_user_sync(SyncConfig())
    except ValueError as exc:
        assert "connection" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def _dry_run_output(osw, **config):
    io = CapturingIO()
    report = run_user_sync(
        SyncConfig(domain="d", dry_run=True, **config),
        osw=osw,
        prompter=Prompter(io.input, io.output),
        session=FakeSession(),
    )
    return report, "\n".join(io.outputs)


def test_preview_lists_skipped_blocked_accounts():
    osw = FakeOsw(extra_users=[{"name": "Mallory", "groups": ["user"], "blockid": 5}])
    _, joined = _dry_run_output(osw)
    assert "Skipped blocked accounts (1): Mallory" in joined
    assert "new=1" in joined  # only the ORCID user


def test_include_blocked_keeps_blocked_accounts():
    osw = FakeOsw(extra_users=[{"name": "Mallory", "groups": ["user"], "blockid": 5}])
    _, joined = _dry_run_output(osw, include_blocked=True)
    assert "Skipped blocked accounts" not in joined
    assert "new=2" in joined


def test_existing_page_at_the_deterministic_title_is_not_created_again():
    uid = user_uuid(MwUser(name=ORCID))
    title = uuid_to_full_page_title(uid)
    stored = SimpleNamespace(
        uuid=uid,
        username=None,
        label=[],
        first_name=None,
        surname=None,
        orcid=None,
        email=set(),
        website=set(),
        organization=set(),
    )
    osw = FakeOsw(existing_pages={title: stored})
    _, joined = _dry_run_output(osw)
    assert osw.loaded == [title]
    assert "new=0" in joined
    assert "gap_fill=1" in joined
