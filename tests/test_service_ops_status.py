"""Unit tests for osw.service.ops.status (Operation.fn called directly).

Importing ``osw.service.ops.status`` registers its operation in
``osw.service.registry.REGISTRY`` at import time, so this module must not
clear the registry the way ``test_service_registry.py`` does.
"""

from unittest.mock import MagicMock

from osw.service import config
from osw.service.context import Context, Policy
from osw.service.ops import status

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


def _clean_env(monkeypatch):
    for var in _ALL_VARS:
        monkeypatch.delenv(var, raising=False)


def test_status_reports_active_instance_and_connects(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "u")
    monkeypatch.setenv("OSW_PASSWORD", "p")
    config.reset()
    ledger = MagicMock()
    ledger.path = "/tmp/ledger.json"
    ledger.entry_count.return_value = 3
    ctx = Context(config.get_settings(), Policy(), osw=MagicMock(), ledger=ledger)

    result = status.status(ctx)

    assert result["connected"] is True
    assert "password" not in result
    assert result["active_iri"] == "wiki.example.org"
    assert result["ledger_entry_count"] == 3
    config.reset()


def test_status_no_active_instance_reports_message(monkeypatch):
    _clean_env(monkeypatch)
    config.reset()
    monkeypatch.setattr(config, "get_settings", lambda: config.Settings(domain=None))
    ctx = Context(config.get_settings(), Policy(), osw=MagicMock(), ledger=MagicMock())

    result = status.status(ctx)

    assert result["connected"] is False
    assert result["active_iri"] is None
    assert "message" in result
    config.reset()


def test_status_connection_failure_reports_connection_error(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "u")
    monkeypatch.setenv("OSW_PASSWORD", "p")
    config.reset()

    from osw.service import context as context_module

    def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(context_module, "OswExpress", _raise)
    ctx = Context(config.get_settings(), Policy(), ledger=MagicMock())

    result = status.status(ctx)

    assert result["connected"] is False
    assert "boom" in result["connection_error"]
    config.reset()
