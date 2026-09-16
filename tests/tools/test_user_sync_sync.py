"""Unit tests for the orchestrator (dry-run path, no live models)."""

from osw.tools.user_sync.config import SyncConfig
from osw.tools.user_sync.interactive import Prompter
from osw.tools.user_sync.sync import SyncReport, run_user_sync

ORCID = "0000-0002-6374-9831"

ORCID_RECORD = {
    "person": {
        "name": {
            "given-names": {"value": "Lukas"},
            "family-name": {"value": "Koschmieder"},
        }
    }
}


class FakeMwSite:
    def api(self, action, **params):
        assert action == "query" and params["list"] == "allusers"
        return {
            "query": {
                "allusers": [
                    {"name": ORCID, "groups": ["user"]},
                    {"name": "SyncBot", "groups": ["user", "bot"]},
                ]
            }
        }


class FakeOsw:
    def __init__(self):
        self.mw_site = FakeMwSite()
        self.store_calls = 0

    def query_instances(self, category):
        return []

    def load_entity(self, titles):
        return []

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


def test_requires_connection():
    try:
        run_user_sync(SyncConfig())
    except ValueError as exc:
        assert "connection" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")
