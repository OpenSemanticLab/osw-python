"""Unit tests for osw.service.context (Policy defaults and Context helpers).

A fake ``osw`` object is injected directly into ``Context`` so these tests
never touch the network.
"""

import sys
from unittest.mock import MagicMock

import pytest
import yaml

from osw.service import config, errors
from osw.service.config import Settings
from osw.service.context import Context, Policy

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
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for var in _ALL_VARS:
        monkeypatch.delenv(var, raising=False)
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("OSW_MCP_ENV_FILE", str(empty))
    config.reset()
    yield
    config.reset()


def _settings(**overrides) -> Settings:
    defaults = dict(domain="wiki.example.org", username="u", password="p")
    defaults.update(overrides)
    return Settings(**defaults)


def _osw_with_page(exists: bool):
    page = MagicMock()
    page.exists = exists
    osw = MagicMock()
    osw.site.get_page.return_value.pages = [page]
    return osw, page


# -- Policy -------------------------------------------------------------
def test_policy_defaults():
    policy = Policy()
    assert policy.capture_stdout is False
    assert policy.errors_as_dicts is False
    assert policy.allow_writes is True
    assert policy.allow_interactive is False


# -- osw / ledger injection ----------------------------------------------
def test_osw_can_be_preset_via_constructor():
    fake = object()
    ctx = Context(_settings(), osw=fake)
    assert ctx.osw is fake


def test_osw_can_be_preset_via_attribute():
    ctx = Context(_settings())
    fake = object()
    ctx.osw = fake
    assert ctx.osw is fake


def test_ledger_can_be_preset_via_constructor():
    fake = object()
    ctx = Context(_settings(), ledger=fake)
    assert ctx.ledger is fake


def test_ledger_can_be_preset_via_attribute():
    ctx = Context(_settings())
    fake = object()
    ctx.ledger = fake
    assert ctx.ledger is fake


def test_osw_property_raises_not_configured_when_no_active_domain(
    monkeypatch, tmp_path
):
    cred_file = tmp_path / "accounts.yaml"
    cred_file.write_text(
        yaml.safe_dump({
            "wiki-a.example.org": {"username": "a", "password": "b"},
            "wiki-b.example.org": {"username": "c", "password": "d"},
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("OSW_CRED_FILEPATH", str(cred_file))
    config.reset()  # two iris in the file: no auto-selection is possible

    ctx = Context(_settings(domain=None, username=None, password=None))

    with pytest.raises(errors.NotConfigured) as exc_info:
        _ = ctx.osw
    assert "OSW_DOMAIN" in str(exc_info.value)
    assert "--instance" in str(exc_info.value)


# -- limit ----------------------------------------------------------------
def test_limit_falls_back_to_settings_max_results():
    ctx = Context(_settings(), osw=object())
    assert ctx.limit(None) == ctx.settings.max_results
    assert ctx.limit(5) == 5


# -- page -------------------------------------------------------------------
def test_page_returns_existing_page():
    osw, page = _osw_with_page(True)
    ctx = Context(_settings(), osw=osw)
    assert ctx.page("Item:OSW1") is page


def test_page_raises_not_found_for_missing_page():
    osw, _page = _osw_with_page(False)
    ctx = Context(_settings(), osw=osw)
    with pytest.raises(errors.NotFound):
        ctx.page("Item:OSW1")


# -- require_write ------------------------------------------------------
def test_require_write_raises_when_writes_disallowed():
    ctx = Context(_settings(), Policy(allow_writes=False), osw=object())
    with pytest.raises(errors.ReadOnly) as exc_info:
        ctx.require_write("create_or_update_entity")
    assert "create_or_update_entity" in str(exc_info.value)
    assert "OSW_READ_ONLY" in str(exc_info.value)
    assert exc_info.value.type == "ReadOnly"
    assert exc_info.value.exit_code == 4


def test_require_write_allows_when_writes_allowed():
    ctx = Context(_settings(), Policy(allow_writes=True), osw=object())
    ctx.require_write("create_or_update_entity")  # must not raise


# -- guard ------------------------------------------------------------------
def test_guard_redirects_stdout_when_capture_stdout_true():
    ctx = Context(_settings(), Policy(capture_stdout=True), osw=object())
    original_stdout = sys.stdout
    with ctx.guard():
        assert sys.stdout is sys.stderr
        assert sys.stdout is not original_stdout
    assert sys.stdout is original_stdout


def test_guard_leaves_stdout_alone_when_capture_stdout_false():
    ctx = Context(_settings(), Policy(capture_stdout=False), osw=object())
    original_stdout = sys.stdout
    with ctx.guard():
        assert sys.stdout is original_stdout


# -- reset / close --------------------------------------------------------
def test_reset_closes_connection_and_drops_osw_and_ledger():
    fake_osw = MagicMock()
    ctx = Context(_settings(), osw=fake_osw, ledger=MagicMock())
    ctx.reset()
    fake_osw.close_connection.assert_called_once()
    assert ctx._osw is None
    assert ctx._ledger is None


def test_reset_survives_close_connection_error():
    fake_osw = MagicMock()
    fake_osw.close_connection.side_effect = RuntimeError("boom")
    ctx = Context(_settings(), osw=fake_osw)
    ctx.reset()  # must not raise
    assert ctx._osw is None


def test_close_calls_reset():
    fake_osw = MagicMock()
    ctx = Context(_settings(), osw=fake_osw)
    ctx.close()
    fake_osw.close_connection.assert_called_once()
