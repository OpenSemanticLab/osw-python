"""Unit tests for osw.service.config (fail-fast credential validation)."""

import os
import sys

import pytest
import yaml
from pydantic import ValidationError

from osw.service import config
from osw.service.config import Settings

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
    # dotenv writes into os.environ directly, so monkeypatch never learns about
    # the variables a loaded .env file introduced and cannot undo them. Left in
    # place they leak into every later test in the session, including other
    # files whose own variable list is narrower than this one.
    for var in _ALL_VARS:
        os.environ.pop(var, None)
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


# -- accounts.pwd.yaml fallback (CLI only) -----------------------------------


def test_cred_file_fallback_in_working_directory(monkeypatch, tmp_path):
    """With discovery enabled, an accounts.pwd.yaml in the working directory
    is used when no credentials are otherwise configured."""
    cred_file = _write_cred_file(
        tmp_path / "accounts.pwd.yaml",
        {"wiki.example.org": {"username": "alice", "password": "secret"}},
    )
    monkeypatch.chdir(tmp_path)
    config.set_env_file_discovery(True)

    settings = config.load()

    assert settings.cred_filepath == str(cred_file)
    assert settings.username is None
    assert settings.password is None


def test_cred_file_fallback_skipped_when_discovery_disabled(monkeypatch, tmp_path):
    """The MCP server never enables discovery, so an accounts.pwd.yaml in its
    working directory (chosen by the MCP client) must not be picked up."""
    _write_cred_file(
        tmp_path / "accounts.pwd.yaml",
        {"wiki.example.org": {"username": "alice", "password": "secret"}},
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError) as exc:
        config.load()
    assert "OSW_USERNAME" in str(exc.value)
    assert "OSW_PASSWORD" in str(exc.value)


def test_explicit_cred_file_wins_over_fallback(monkeypatch, tmp_path):
    _write_cred_file(
        tmp_path / "accounts.pwd.yaml",
        {"wiki.example.org": {"username": "alice", "password": "secret"}},
    )
    explicit = _write_cred_file(
        tmp_path / "explicit.yaml",
        {"wiki.example.org": {"username": "bob", "password": "other"}},
    )
    monkeypatch.setenv("OSW_CRED_FILEPATH", str(explicit))
    monkeypatch.chdir(tmp_path)
    config.set_env_file_discovery(True)

    settings = config.load()

    assert settings.cred_filepath == str(explicit)


def test_cred_file_fallback_skipped_when_username_password_configured(
    monkeypatch, tmp_path
):
    # The fallback only fills a gap; a credential file entry can carry a
    # different user name, so it must never override explicit credentials.
    _write_cred_file(
        tmp_path / "accounts.pwd.yaml",
        {"wiki.example.org": {"username": "alice", "password": "secret"}},
    )
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.chdir(tmp_path)
    config.set_env_file_discovery(True)

    settings = config.load()

    assert settings.cred_filepath is None


def test_cred_file_fallback_skipped_when_only_username_configured(
    monkeypatch, tmp_path
):
    # Any explicitly named credential means the operator intends to
    # authenticate that way; a half-configured pair must raise rather than
    # silently switch to a different identity via the fallback file.
    _write_cred_file(
        tmp_path / "accounts.pwd.yaml",
        {"wiki.example.org": {"username": "alice", "password": "secret"}},
    )
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.chdir(tmp_path)
    config.set_env_file_discovery(True)

    with pytest.raises(RuntimeError) as exc:
        config.load()

    assert "OSW_PASSWORD" in str(exc.value)


def test_discovered_cred_file_wrong_domain_discarded_when_not_strict(
    monkeypatch, tmp_path
):
    # A discovered accounts.pwd.yaml is a convenience, not something the
    # operator configured, so a domain mismatch discards it instead of
    # raising: load(strict=False) exists precisely so a status command can
    # report "not configured" rather than crash.
    _write_cred_file(
        tmp_path / "accounts.pwd.yaml",
        {"other.example.org": {"username": "alice", "password": "secret"}},
    )
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.chdir(tmp_path)
    config.set_env_file_discovery(True)

    settings = config.load(strict=False)

    assert settings.cred_filepath is None


def test_discovered_cred_file_wrong_domain_raises_when_strict(monkeypatch, tmp_path):
    _write_cred_file(
        tmp_path / "accounts.pwd.yaml",
        {"other.example.org": {"username": "alice", "password": "secret"}},
    )
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.chdir(tmp_path)
    config.set_env_file_discovery(True)

    with pytest.raises(RuntimeError) as exc:
        config.load()

    assert "accounts.pwd.yaml" in str(exc.value)
    assert "wiki.example.org" in str(exc.value)


def test_discovered_cred_file_wrong_domain_records_rejected_origin(
    monkeypatch, tmp_path
):
    # The rejection must be visible in the module state, not just discarded
    # locally, so log_config_sources (which runs before load()) can report
    # the same outcome load() then acts on.
    cred_file = _write_cred_file(
        tmp_path / "accounts.pwd.yaml",
        {"other.example.org": {"username": "alice", "password": "secret"}},
    )
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.chdir(tmp_path)
    config.set_env_file_discovery(True)

    config.load(strict=False)

    assert config._cred_file_origin == "rejected"
    assert config._cred_file_path == str(cred_file)


def test_no_upward_walk_for_cred_file_fallback(monkeypatch, tmp_path):
    """The accounts.pwd.yaml fallback must not walk to parent directories,
    unlike the .env search, which does."""
    _write_cred_file(
        tmp_path / "accounts.pwd.yaml",
        {"wiki.example.org": {"username": "alice", "password": "secret"}},
    )
    child = tmp_path / "child"
    child.mkdir()
    monkeypatch.chdir(child)
    config.set_env_file_discovery(True)

    with pytest.raises(RuntimeError) as exc:
        config.load()

    assert "OSW_USERNAME" in str(exc.value)
    assert "OSW_PASSWORD" in str(exc.value)


def test_missing_credentials_error_mentions_fallback_when_discovery_enabled(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    config.set_env_file_discovery(True)

    with pytest.raises(RuntimeError) as exc:
        config.load()

    assert "accounts.pwd.yaml" in str(exc.value)


def test_missing_credentials_error_omits_fallback_when_discovery_disabled(monkeypatch):
    with pytest.raises(RuntimeError) as exc:
        config.load()

    assert "accounts.pwd.yaml" not in str(exc.value)


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


def test_log_config_sources_reports_fallback_cred_file(monkeypatch, tmp_path, capsys):
    _write_cred_file(
        tmp_path / "accounts.pwd.yaml",
        {"wiki.example.org": {"username": "u", "password": "p"}},
    )
    monkeypatch.chdir(tmp_path)
    config.set_env_file_discovery(True)

    config.log_config_sources()

    captured = capsys.readouterr()
    assert "accounts.pwd.yaml found in the working directory" in captured.err


def test_log_config_sources_reports_rejected_cred_file(monkeypatch, tmp_path, capsys):
    # The banner must name the rejection, not just the file: load() rejects
    # this same file right after, so claiming it is "in use" would be wrong.
    cred_file = _write_cred_file(
        tmp_path / "accounts.pwd.yaml",
        {"other.example.org": {"username": "u", "password": "p"}},
    )
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.chdir(tmp_path)
    config.set_env_file_discovery(True)

    config.log_config_sources()

    captured = capsys.readouterr()
    assert str(cred_file) in captured.err
    assert "ignored: no entry for domain" in captured.err
    assert "wiki.example.org" in captured.err


def test_log_config_sources_reports_cred_file_from_env_file(
    monkeypatch, tmp_path, capsys
):
    cred = tmp_path / "accounts.yaml"
    cred.write_text(
        yaml.safe_dump({"wiki.example.org": {"username": "u", "password": "p"}}),
        encoding="utf-8",
    )
    env = tmp_path / "creds.env"
    env.write_text(f"OSW_CRED_FILEPATH={cred}\n", encoding="utf-8")
    monkeypatch.setenv("OSW_ENV_FILE", str(env))

    config.log_config_sources()

    captured = capsys.readouterr()
    assert "from OSW_CRED_FILEPATH in the env file" in captured.err


def test_env_file_attribution_survives_a_second_load(monkeypatch, tmp_path, capsys):
    # A repeated _load_env_file() call within the same process must not erase
    # the attribution of a name the file introduced on the first call: the
    # name is already in os.environ by then, so a second before/after diff
    # would otherwise come up empty.
    cred = tmp_path / "accounts.yaml"
    cred.write_text(
        yaml.safe_dump({"wiki.example.org": {"username": "u", "password": "p"}}),
        encoding="utf-8",
    )
    env = tmp_path / "creds.env"
    env.write_text(f"OSW_CRED_FILEPATH={cred}\n", encoding="utf-8")
    monkeypatch.setenv("OSW_ENV_FILE", str(env))

    config._load_env_file()
    config._load_env_file()
    config.log_config_sources()

    captured = capsys.readouterr()
    assert "from OSW_CRED_FILEPATH in the env file" in captured.err


def test_log_config_sources_reports_cred_file_from_environment(
    monkeypatch, tmp_path, capsys
):
    cred = tmp_path / "accounts.yaml"
    cred.write_text(
        yaml.safe_dump({"wiki.example.org": {"username": "u", "password": "p"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OSW_CRED_FILEPATH", str(cred))

    config.log_config_sources()

    captured = capsys.readouterr()
    assert "from the OSW_CRED_FILEPATH environment variable" in captured.err


def test_log_config_sources_verbose_false_prints_only_credential_line(
    monkeypatch, capsys
):
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")

    config.log_config_sources(verbose=False)

    captured = capsys.readouterr()
    lines = captured.err.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("[osw] credentials    :")


def test_log_config_sources_verbose_true_prints_both_lines_credential_first(
    monkeypatch, capsys
):
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")

    config.log_config_sources()

    captured = capsys.readouterr()
    lines = captured.err.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("[osw] credentials    :")
    assert lines[1].startswith("[osw] env file       :")


def test_log_config_sources_reports_username_password_from_env_file(
    monkeypatch, tmp_path, capsys
):
    env = tmp_path / "creds.env"
    env.write_text("OSW_USERNAME=alice\nOSW_PASSWORD=secret\n", encoding="utf-8")
    monkeypatch.setenv("OSW_ENV_FILE", str(env))

    config.log_config_sources()

    captured = capsys.readouterr()
    assert "OSW_USERNAME/OSW_PASSWORD (from the env file)" in captured.err


def test_log_config_sources_reports_username_password_from_environment(
    monkeypatch, capsys
):
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")

    config.log_config_sources()

    captured = capsys.readouterr()
    assert "OSW_USERNAME/OSW_PASSWORD (from the environment)" in captured.err


def test_log_config_sources_reports_credentials_not_configured(monkeypatch, capsys):
    config.log_config_sources()

    captured = capsys.readouterr()
    assert (
        "not configured (set OSW_CRED_FILEPATH, or OSW_USERNAME/OSW_PASSWORD)"
        in captured.err
    )


def test_log_env_file_source_prints_only_env_file_line(monkeypatch, tmp_path, capsys):
    env = tmp_path / "creds.env"
    env.write_text("", encoding="utf-8")
    monkeypatch.setenv("OSW_ENV_FILE", str(env))
    config._load_env_file()

    config.log_env_file_source()

    captured = capsys.readouterr()
    lines = captured.err.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("[osw] env file       :")
    assert str(env) in lines[0]


def test_missing_credentials_message_has_stdio_hint_when_discovery_disabled(
    monkeypatch,
):
    with pytest.raises(RuntimeError) as exc:
        config.load()

    assert "stdio transport" in str(exc.value)


def test_missing_credentials_message_omits_stdio_hint_when_discovery_enabled(
    monkeypatch, tmp_path
):
    # chdir away from the repo root: it has its own accounts.pwd.yaml for local
    # dev, which discovery would otherwise pick up and satisfy the check with.
    monkeypatch.chdir(tmp_path)
    config.set_env_file_discovery(True)

    with pytest.raises(RuntimeError) as exc:
        config.load()

    assert "stdio transport" not in str(exc.value)


# -- Settings validation (pydantic) ------------------------------------------


def test_blank_max_results_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_MAX_RESULTS", "   ")
    settings = config.load()
    assert settings.max_results == 100


def test_zero_max_results_raises(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_MAX_RESULTS", "0")
    with pytest.raises(RuntimeError) as exc:
        config.load()
    assert "OSW_MAX_RESULTS" in str(exc.value)


def test_malformed_sparql_endpoint_raises(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_SPARQL_ENDPOINT", "not a url")
    with pytest.raises(RuntimeError) as exc:
        config.load()
    assert "OSW_SPARQL_ENDPOINT" in str(exc.value)


def test_valid_sparql_endpoint_loads(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_SPARQL_ENDPOINT", "https://wiki.example.org/sparql")
    settings = config.load()
    assert settings.sparql_endpoint == "https://wiki.example.org/sparql"


def test_error_names_the_alias_that_was_set(monkeypatch):
    # Only the alias is set (not the canonical name), so the error must name
    # the alias, not the canonical variable, for the operator to find it.
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_MCP_MAX_RESULTS", "notanumber")
    with pytest.raises(RuntimeError) as exc:
        config.load()
    assert "OSW_MCP_MAX_RESULTS" in str(exc.value)


def test_misspelled_read_only_raises(monkeypatch):
    # A typo must not silently enable writes: read_only is the one flag whose
    # fail-open default is dangerous, so an unparseable value has to be loud.
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_READ_ONLY", "ture")
    with pytest.raises(RuntimeError) as exc:
        config.load()
    assert "OSW_READ_ONLY" in str(exc.value)


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "on", "y", "t"])
def test_read_only_truthy_spellings(monkeypatch, raw):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_READ_ONLY", raw)
    assert config.load().read_only is True


@pytest.mark.parametrize("raw", ["0", "false", "FALSE", "no", "off", "n", "f"])
def test_read_only_falsy_spellings(monkeypatch, raw):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_READ_ONLY", raw)
    assert config.load().read_only is False


def test_blank_read_only_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_READ_ONLY", "   ")
    assert config.load().read_only is False


def test_read_only_error_names_the_alias_that_was_set(monkeypatch):
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "alice")
    monkeypatch.setenv("OSW_PASSWORD", "secret")
    monkeypatch.setenv("OSW_MCP_READ_ONLY", "disabled")
    with pytest.raises(RuntimeError) as exc:
        config.load()
    assert "OSW_MCP_READ_ONLY" in str(exc.value)


def test_domain_with_whitespace_rejected():
    with pytest.raises(ValidationError):
        Settings(domain="wiki.example.org has a space")


def test_domain_as_full_url_accepted():
    # get_active_domain() relies on a full URL being a legal domain value.
    settings = Settings(domain="https://wiki.example.org/w/")
    assert settings.domain == "https://wiki.example.org/w/"


def test_settings_is_frozen():
    settings = Settings(domain="wiki.example.org")
    with pytest.raises(ValidationError):
        settings.domain = "other.example.org"
