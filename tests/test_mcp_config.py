"""Unit tests for osw.mcp.config (fail-fast credential validation)."""

import pytest
import yaml

pytest.importorskip("mcp", reason="requires the osw[mcp] extra")
pytest.importorskip("dotenv", reason="requires the osw[mcp] extra")

from osw.mcp import config

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


def _write_cred_file(path, data):
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_cred_file_configured_and_present_no_env_credentials(monkeypatch, tmp_path):
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {"wiki.example.org": {"username": "alice", "password": "secret"}},
    )
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))
    settings = config.load()
    assert settings.domain == "wiki.example.org"
    assert settings.cred_filepath == str(cred_file)
    assert settings.username is None
    assert settings.password is None


def test_cred_file_missing_raises(monkeypatch, tmp_path):
    missing = tmp_path / "does-not-exist.yaml"
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(missing))
    with pytest.raises(RuntimeError) as exc:
        config.load()
    assert str(missing) in str(exc.value)


def test_missing_username_password_without_cred_file_raises(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    with pytest.raises(RuntimeError) as exc:
        config.load()
    assert "OSW_USERNAME" in str(exc.value)
    assert "OSW_PASSWORD" in str(exc.value)
    assert "OSW_DOMAIN" not in str(exc.value)


def test_username_password_still_work_with_no_cred_file(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    settings = config.load()
    assert settings.domain == "wiki.example.org"
    assert settings.username == "alice"
    assert settings.cred_filepath is None


def test_redacted_never_contains_password_or_credential_value(monkeypatch, tmp_path):
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {"wiki.example.org": {"username": "alice", "password": "supersecret"}},
    )
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))
    settings = config.load()
    redacted = settings.redacted()
    assert "password" not in redacted
    assert "supersecret" not in str(redacted)
    assert redacted["cred_filepath_configured"] is True


def test_cred_file_missing_domain_entry_raises(monkeypatch, tmp_path):
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {"other.example.org": {"username": "alice", "password": "secret"}},
    )
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))
    with pytest.raises(RuntimeError) as exc:
        config.load()
    assert "other.example.org" in str(exc.value)
    assert "wiki.example.org" in str(exc.value)


def test_cred_file_without_domain_is_legal(monkeypatch, tmp_path):
    # With a usable credential file, a missing domain is no longer an error:
    # which instance to use is chosen later (auto-selected or via
    # select_instance).
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {
            "wiki-a.example.org": {"username": "alice", "password": "secret"},
            "wiki-b.example.org": {"username": "bob", "password": "secret2"},
        },
    )
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))
    settings = config.load()
    assert settings.domain is None
    assert settings.cred_filepath == str(cred_file)


def test_cred_file_without_domain_skips_domain_verification(monkeypatch, tmp_path):
    # No domain configured means there is nothing to verify at startup, even
    # though the file does not contain an entry named after any particular
    # domain the caller might later select.
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {"wiki-a.example.org": {"username": "alice", "password": "secret"}},
    )
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))
    settings = config.load()
    assert settings.domain is None
