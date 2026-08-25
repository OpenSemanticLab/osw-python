"""Unit tests for multi-instance selection in osw.mcp (config + connection).

These are fully offline: no network, no live wiki.
"""

import pytest
import yaml

pytest.importorskip("mcp", reason="requires the osw[mcp] extra")
pytest.importorskip("dotenv", reason="requires the osw[mcp] extra")

from osw.mcp import connection
from osw.service import config

_ALL_VARS = [
    "OSW_DOMAIN",
    "OSL_DOMAIN",
    "OSW_USERNAME",
    "OSL_USERNAME",
    "OSW_PASSWORD",
    "OSL_PASSWORD",
    "OSW_MCP_CRED_FILEPATH",
    "OSL_CRED_FILEPATH",
    "OSW_SPARQL_ENDPOINT",
    "OSW_MCP_READ_ONLY",
    "OSW_MCP_STATE_DIR",
    "OSW_MCP_MAX_RESULTS",
    "OSW_MCP_MAX_CHARS",
    "OSW_MCP_ENV_FILE",
]


class FakeMCP:
    """Minimal stand-in that captures @tool-decorated functions by name."""

    def __init__(self):
        self.tools = {}

    def tool(self, *_a, **_k):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn

        return deco


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for var in _ALL_VARS:
        monkeypatch.delenv(var, raising=False)
    # Point dotenv at an empty file so it never picks up a real .env on disk
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("OSW_MCP_ENV_FILE", str(empty))
    config.reset()
    connection._osw = None
    connection._ledger = None
    yield
    config.reset()
    connection._osw = None
    connection._ledger = None


def _write_cred_file(path, data):
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


# -- auto-selection ---------------------------------------------------------
def test_auto_select_from_configured_domain(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")

    assert config.get_active_iri() == "wiki.example.org"
    assert config.get_active_domain() == "wiki.example.org"


def test_auto_select_single_iri_cred_file(monkeypatch, tmp_path):
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {"wiki-dev.open-semantic-lab.org": {"username": "a", "password": "b"}},
    )
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))

    assert config.get_active_iri() == "wiki-dev.open-semantic-lab.org"
    assert config.get_active_domain() == "wiki-dev.open-semantic-lab.org"


def test_no_auto_select_with_multiple_iris(monkeypatch, tmp_path):
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {
            "wiki-a.example.org": {"username": "a", "password": "b"},
            "wiki-b.example.org": {"username": "c", "password": "d"},
        },
    )
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))

    assert config.get_active_iri() is None
    assert config.get_active_domain() is None


# -- set_active_instance / select_instance ----------------------------------
def test_set_active_instance_valid(monkeypatch, tmp_path):
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {
            "wiki-a.example.org": {"username": "a", "password": "b"},
            "wiki-b.example.org": {"username": "c", "password": "d"},
        },
    )
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))

    config.set_active_instance("wiki-b.example.org")

    assert config.get_active_iri() == "wiki-b.example.org"
    assert config.get_active_domain() == "wiki-b.example.org"


def test_set_active_instance_unknown_iri_raises(monkeypatch, tmp_path):
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {"wiki-a.example.org": {"username": "a", "password": "b"}},
    )
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))

    with pytest.raises(ValueError) as exc:
        config.set_active_instance("does-not-exist.example.org")
    assert "wiki-a.example.org" in str(exc.value)


# -- get_osw() / run_guarded without an active instance ----------------------
def test_get_osw_raises_when_no_instance_selected(monkeypatch, tmp_path):
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {
            "wiki-a.example.org": {"username": "a", "password": "b"},
            "wiki-b.example.org": {"username": "c", "password": "d"},
        },
    )
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))

    with pytest.raises(RuntimeError) as exc:
        connection.get_osw()
    assert "No OSL instance selected" in str(exc.value)
    assert "wiki-a.example.org" in str(exc.value)
    assert "wiki-b.example.org" in str(exc.value)


def test_run_guarded_surfaces_no_instance_selected_as_structured_dict(
    monkeypatch, tmp_path
):
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {
            "wiki-a.example.org": {"username": "a", "password": "b"},
            "wiki-b.example.org": {"username": "c", "password": "d"},
        },
    )
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))

    result = connection.run_guarded(lambda osw: {"ok": True})

    assert result["type"] == "RuntimeError"
    assert "No OSL instance selected" in result["error"]


# -- domain derivation helper -------------------------------------------------
def test_derive_domain_from_bare_domain():
    assert (
        config._derive_domain("wiki-dev.open-semantic-lab.org")
        == "wiki-dev.open-semantic-lab.org"
    )


def test_derive_domain_from_full_url():
    assert (
        config._derive_domain("https://wiki-dev.open-semantic-lab.org/w/")
        == "wiki-dev.open-semantic-lab.org"
    )


# -- connection.reset() drops the ledger -------------------------------------
def test_reset_drops_ledger_for_new_domain_after_switching(monkeypatch, tmp_path):
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {
            "wiki-a.example.org": {"username": "a", "password": "b"},
            "wiki-b.example.org": {"username": "c", "password": "d"},
        },
    )
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))
    monkeypatch.setenv("OSW_MCP_STATE_DIR", str(tmp_path / "state"))
    config.set_active_instance("wiki-a.example.org")

    ledger_a = connection.get_ledger()
    assert "wiki-a.example.org" in str(ledger_a.path)

    config.set_active_instance("wiki-b.example.org")
    connection.reset()
    ledger_b = connection.get_ledger()

    assert "wiki-b.example.org" in str(ledger_b.path)
    assert ledger_a.path != ledger_b.path


# -- get_active_credentials ---------------------------------------------------
def test_get_active_credentials_from_cred_file(monkeypatch, tmp_path):
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {"wiki-a.example.org": {"username": "alice", "password": "s3cret"}},
    )
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))

    assert config.get_active_iri() == "wiki-a.example.org"
    assert config.get_active_credentials() == ("alice", "s3cret")


def test_get_active_credentials_follows_instance_switch(monkeypatch, tmp_path):
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {
            "wiki-a.example.org": {"username": "alice", "password": "a-pw"},
            "wiki-b.example.org": {"username": "bob", "password": "b-pw"},
        },
    )
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))
    config.set_active_instance("wiki-a.example.org")
    assert config.get_active_credentials() == ("alice", "a-pw")

    config.set_active_instance("wiki-b.example.org")

    assert config.get_active_credentials() == ("bob", "b-pw")


def test_get_active_credentials_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")

    assert config.get_active_credentials() == ("alice", "secret")


def test_get_active_credentials_returns_none_none_without_raising(monkeypatch):
    # A domain-only, cred-file-less, credential-less settings object cannot be
    # produced through config.load() itself (it would raise); construct it
    # directly to exercise the "nothing resolves" path of get_active_credentials.
    monkeypatch.setattr(
        config, "get_settings", lambda: config.Settings(domain="wiki.example.org")
    )

    assert config.get_active_credentials() == (None, None)
