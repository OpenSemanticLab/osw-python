"""Unit tests for osw.service.config (fail-fast credential validation)."""

import sys

import pytest
import yaml

from osw.service import config

_ALL_VARS = [
    "OSW_DOMAIN",
    "OSL_DOMAIN",
    "OSW_USERNAME",
    "OSL_USERNAME",
    "OSW_PASSWORD",
    "OSL_PASSWORD",
    "OSW_CRED_FILEPATH",
    "OSW_MCP_CRED_FILEPATH",
    "OSL_CRED_FILEPATH",
    "OSW_SPARQL_ENDPOINT",
    "OSW_READ_ONLY",
    "OSW_MCP_READ_ONLY",
    "OSW_STATE_DIR",
    "OSW_MCP_STATE_DIR",
    "OSW_MAX_RESULTS",
    "OSW_MCP_MAX_RESULTS",
    "OSW_MAX_CHARS",
    "OSW_MCP_MAX_CHARS",
    "OSW_ENV_FILE",
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


# -- canonical OSW_* names --------------------------------------------------


def test_canonical_cred_filepath(monkeypatch, tmp_path):
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {"wiki.example.org": {"username": "alice", "password": "secret"}},
    )
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_CRED_FILEPATH", str(cred_file))
    settings = config.load()
    assert settings.cred_filepath == str(cred_file)


def test_canonical_read_only(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_READ_ONLY", "true")
    settings = config.load()
    assert settings.read_only is True


def test_canonical_state_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    state_dir = str(tmp_path / "state")
    monkeypatch.setenv("OSW_STATE_DIR", state_dir)
    settings = config.load()
    assert settings.state_dir == state_dir


def test_canonical_max_results(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_MAX_RESULTS", "7")
    settings = config.load()
    assert settings.max_results == 7


def test_canonical_max_chars(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_MAX_CHARS", "12345")
    settings = config.load()
    assert settings.max_chars == 12345


def test_canonical_env_file(monkeypatch, tmp_path):
    env = tmp_path / "creds.env"
    env.write_text(
        "OSW_DOMAIN=fromfile.example.org\nOSW_USERNAME=fileuser\nOSW_PASSWORD=filepw\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OSW_MCP_ENV_FILE", raising=False)
    monkeypatch.setenv("OSW_ENV_FILE", str(env))
    settings = config.load()
    assert settings.domain == "fromfile.example.org"
    assert settings.username == "fileuser"


# -- OSW_MCP_* aliases not already covered above ----------------------------


def test_alias_state_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    state_dir = str(tmp_path / "state")
    monkeypatch.setenv("OSW_MCP_STATE_DIR", state_dir)
    settings = config.load()
    assert settings.state_dir == state_dir


def test_alias_max_chars(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_MCP_MAX_CHARS", "54321")
    settings = config.load()
    assert settings.max_chars == 54321


# -- canonical wins when both canonical and alias are set --------------------


def test_canonical_wins_over_alias(monkeypatch, tmp_path):
    cred_file = _write_cred_file(
        tmp_path / "accounts.yaml",
        {"wiki.example.org": {"username": "alice", "password": "secret"}},
    )
    other_cred_file = _write_cred_file(
        tmp_path / "other.yaml",
        {"wiki.example.org": {"username": "alice", "password": "secret"}},
    )
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_CRED_FILEPATH", str(cred_file))
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(other_cred_file))
    monkeypatch.setenv("OSW_READ_ONLY", "true")
    monkeypatch.setenv("OSW_MCP_READ_ONLY", "false")
    monkeypatch.setenv("OSW_MAX_RESULTS", "1")
    monkeypatch.setenv("OSW_MCP_MAX_RESULTS", "2")
    monkeypatch.setenv("OSW_MAX_CHARS", "10")
    monkeypatch.setenv("OSW_MCP_MAX_CHARS", "20")
    state_dir = str(tmp_path / "state")
    other_state_dir = str(tmp_path / "other-state")
    monkeypatch.setenv("OSW_STATE_DIR", state_dir)
    monkeypatch.setenv("OSW_MCP_STATE_DIR", other_state_dir)

    settings = config.load()

    assert settings.cred_filepath == str(cred_file)
    assert settings.read_only is True
    assert settings.max_results == 1
    assert settings.max_chars == 10
    assert settings.state_dir == state_dir


def test_canonical_env_file_wins_over_alias(monkeypatch, tmp_path):
    canonical_env = tmp_path / "canonical.env"
    canonical_env.write_text("OSW_DOMAIN=canonical.example.org\n", encoding="utf-8")
    alias_env = tmp_path / "alias.env"
    alias_env.write_text("OSW_DOMAIN=alias.example.org\n", encoding="utf-8")
    monkeypatch.setenv("OSW_ENV_FILE", str(canonical_env))
    monkeypatch.setenv("OSW_MCP_ENV_FILE", str(alias_env))
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")

    settings = config.load()

    assert settings.domain == "canonical.example.org"


# -- strict=False ------------------------------------------------------------


def test_load_not_strict_returns_settings_without_raising(monkeypatch):
    settings = config.load(strict=False)
    assert settings.domain is None
    assert settings.username is None
    assert settings.password is None


def test_load_not_strict_still_raises_on_invalid_int(monkeypatch):
    monkeypatch.setenv("OSW_MAX_RESULTS", "notanumber")
    with pytest.raises(RuntimeError):
        config.load(strict=False)


def test_load_not_strict_still_raises_on_missing_cred_file(monkeypatch, tmp_path):
    missing = tmp_path / "does-not-exist.yaml"
    monkeypatch.setenv("OSW_CRED_FILEPATH", str(missing))
    with pytest.raises(RuntimeError) as exc:
        config.load(strict=False)
    assert str(missing) in str(exc.value)


# -- _load_env_file / optional dotenv ----------------------------------------


def test_load_env_file_raises_when_configured_and_dotenv_missing(monkeypatch, tmp_path):
    env = tmp_path / "creds.env"
    env.write_text("OSW_DOMAIN=wiki.example.org\n", encoding="utf-8")
    monkeypatch.setenv("OSW_ENV_FILE", str(env))
    monkeypatch.setitem(sys.modules, "dotenv", None)
    with pytest.raises(RuntimeError) as exc:
        config._load_env_file()
    assert "OSW_ENV_FILE" in str(exc.value)
    assert "python-dotenv" in str(exc.value)


def test_load_env_file_silent_when_not_configured_and_dotenv_missing(
    monkeypatch,
):
    monkeypatch.delenv("OSW_MCP_ENV_FILE", raising=False)
    monkeypatch.delenv("OSW_ENV_FILE", raising=False)
    monkeypatch.setitem(sys.modules, "dotenv", None)
    # must not raise
    config._load_env_file()


# -- implicit .env discovery ----------------------------------------------------
def test_no_implicit_env_search_by_default(monkeypatch, tmp_path):
    """Discovery is off unless an adapter opts in, so a stray .env in the
    working directory cannot decide which instance a server connects to."""
    monkeypatch.delenv("OSW_MCP_ENV_FILE", raising=False)
    monkeypatch.delenv("OSW_ENV_FILE", raising=False)
    (tmp_path / ".env").write_text(
        "OSW_DOMAIN=from-cwd.example.org\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    config._load_env_file()

    assert config._first_env(config.ENV_DOMAIN) is None
    assert config._env_file_origin == "not searched"


def test_implicit_env_search_starts_at_the_working_directory(monkeypatch, tmp_path):
    """The search must start at the CWD, not at this module's directory.

    ``dotenv.load_dotenv()`` with no arguments walks up from the *calling
    module's* file, which is osw/service/config.py: under an editable install
    that is the osw checkout, so it would silently load the checkout's own
    .env no matter where the user is standing.
    """
    monkeypatch.delenv("OSW_MCP_ENV_FILE", raising=False)
    monkeypatch.delenv("OSW_ENV_FILE", raising=False)
    nested = tmp_path / "project" / "sub"
    nested.mkdir(parents=True)
    (tmp_path / "project" / ".env").write_text(
        "OSW_DOMAIN=from-cwd.example.org\n", encoding="utf-8"
    )
    monkeypatch.chdir(nested)
    config.set_env_file_discovery(True)

    config._load_env_file()

    assert config._first_env(config.ENV_DOMAIN) == "from-cwd.example.org"
    assert config._env_file_origin == "discovered"


def test_explicit_env_file_wins_over_discovery(monkeypatch, tmp_path):
    explicit = tmp_path / "explicit.env"
    explicit.write_text("OSW_DOMAIN=explicit.example.org\n", encoding="utf-8")
    (tmp_path / ".env").write_text(
        "OSW_DOMAIN=from-cwd.example.org\n", encoding="utf-8"
    )
    monkeypatch.setenv("OSW_ENV_FILE", str(explicit))
    monkeypatch.chdir(tmp_path)
    config.set_env_file_discovery(True)

    config._load_env_file()

    assert config._first_env(config.ENV_DOMAIN) == "explicit.example.org"
    assert config._env_file_origin == "explicit"


def test_set_env_file_discovery_raises_only_on_a_late_change(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "u")
    monkeypatch.setenv("OSW_PASSWORD", "p")
    config.get_settings()  # populates the cache

    config.set_env_file_discovery(False)  # re-asserting the current value is fine

    with pytest.raises(RuntimeError, match="before settings are loaded"):
        config.set_env_file_discovery(True)


# -- .env escape footgun --------------------------------------------------------
def test_missing_cred_file_flags_an_escape_mangled_path(monkeypatch):
    r"""A double-quoted Windows path in .env loses \a to a BEL byte.

    The mangled path then renders as if it were the path the user typed, so
    the plain "does not exist" message looks wrong rather than informative.
    """
    # What dotenv produces for OSW_CRED_FILEPATH="C:\dir\accounts.yaml":
    # the \a is decoded to BEL, which prints as nothing.
    mangled = "C:" + chr(92) + "dir" + chr(7) + "ccounts.yaml"
    monkeypatch.setenv("OSW_CRED_FILEPATH", mangled)

    with pytest.raises(RuntimeError) as exc:
        config.load()

    assert "control character" in str(exc.value)
    assert "single quotes" in str(exc.value)


def test_missing_cred_file_without_control_chars_has_no_escape_hint(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("OSW_CRED_FILEPATH", str(tmp_path / "nope.yaml"))

    with pytest.raises(RuntimeError) as exc:
        config.load()

    assert "does not exist" in str(exc.value)
    assert "control character" not in str(exc.value)


# -- startup banner -------------------------------------------------------------
def test_log_config_sources_reports_env_and_cred_file(monkeypatch, tmp_path, capsys):
    cred = tmp_path / "accounts.yaml"
    cred.write_text(
        yaml.safe_dump({"wiki.example.org": {"username": "u", "password": "p"}}),
        encoding="utf-8",
    )
    env = tmp_path / "creds.env"
    env.write_text("", encoding="utf-8")
    monkeypatch.setenv("OSW_ENV_FILE", str(env))
    monkeypatch.setenv("OSW_CRED_FILEPATH", str(cred))
    config._load_env_file()

    config.log_config_sources()

    captured = capsys.readouterr()
    # stdout is the JSON-RPC stream under MCP and the result payload under
    # `osw --json`, so the banner must never appear there.
    assert captured.out == ""
    assert str(env) in captured.err
    assert str(cred) in captured.err


def test_log_config_sources_omits_cred_file_when_unconfigured(monkeypatch, capsys):
    config._load_env_file()

    config.log_config_sources()

    captured = capsys.readouterr()
    assert "env file" in captured.err
    assert "credential file" not in captured.err
