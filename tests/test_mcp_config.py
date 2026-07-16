"""Unit tests for osw.mcp.config (fail-fast credential validation)."""

import pytest

from osw.mcp import config

_ALL_VARS = [
    "OSW_DOMAIN",
    "OSL_DOMAIN",
    "OSW_USERNAME",
    "OSL_USERNAME",
    "OSW_PASSWORD",
    "OSL_PASSWORD",
    "OSW_SPARQL_ENDPOINT",
    "OSW_MCP_READ_ONLY",
    "OSW_MCP_STATE_DIR",
    "OSW_MCP_MAX_RESULTS",
    "OSW_MCP_MAX_CHARS",
    "OSW_MCP_ENV_FILE",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for var in _ALL_VARS:
        monkeypatch.delenv(var, raising=False)
    # Point dotenv at an empty file so it never picks up a real .env on disk
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("OSW_MCP_ENV_FILE", str(empty))
    config.reset()
    yield
    config.reset()


def test_missing_credentials_raise(monkeypatch):
    with pytest.raises(RuntimeError) as exc:
        config.load()
    # message names the missing vars so the operator can fix it
    assert "OSW_DOMAIN" in str(exc.value)
    assert "OSW_USERNAME" in str(exc.value)
    assert "OSW_PASSWORD" in str(exc.value)


def test_missing_credentials_do_not_prompt(monkeypatch):
    # If load() ever fell through to input()/getpass, this would hang; a raise
    # proves it fails fast instead.
    def _boom(*_a, **_k):
        raise AssertionError("interactive prompt must never be reached")

    monkeypatch.setattr("builtins.input", _boom)
    with pytest.raises(RuntimeError):
        config.load()


def test_valid_credentials_parse(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_MCP_READ_ONLY", "TRUE")
    monkeypatch.setenv("OSW_MCP_MAX_RESULTS", "42")
    settings = config.load()
    assert settings.domain == "wiki.example.org"
    assert settings.username == "alice"
    assert settings.read_only is True
    assert settings.max_results == 42
    # password must not appear in the redacted view
    assert "password" not in settings.redacted()
    assert "secret" not in repr(settings)


def test_osl_fallback(monkeypatch):
    monkeypatch.setenv("OSL_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSL_USERNAME", "bob")
    monkeypatch.setenv("OSL_PASSWORD", "pw")
    settings = config.load()
    assert settings.domain == "wiki.example.org"
    assert settings.username == "bob"


def test_env_file_override(monkeypatch, tmp_path):
    env = tmp_path / "creds.env"
    env.write_text(
        "OSW_DOMAIN=fromfile.example.org\nOSW_USERNAME=fileuser\nOSW_PASSWORD=filepw\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OSW_MCP_ENV_FILE", str(env))
    settings = config.load()
    assert settings.domain == "fromfile.example.org"
    assert settings.username == "fileuser"


def test_invalid_int_raises(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_MCP_MAX_RESULTS", "notanumber")
    with pytest.raises(RuntimeError):
        config.load()
