"""Registration-shape tests for the osw-mcp server: which tools end up
registered on a real ``MCPServer``, not what any individual tool body does
(see ``tests/test_service_ops_*.py`` for that) and not the pure
``Operation`` -> ``mcp.tool()`` kwargs mapping (see
``tests/test_mcp_registration.py`` for that).

These are fully offline: no network, no live wiki.
"""

from __future__ import annotations

import asyncio
import io

import pytest
import yaml

from osw.mcp import server
from osw.service import config
from osw.service.registry import iter_operations

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
    "OSW_READ_ONLY",
    "OSW_MCP_READ_ONLY",
    "OSW_MCP_ENV_FILE",
    "OSW_VERBOSE",
    "OSW_MCP_VERBOSE",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for var in _ALL_VARS:
        monkeypatch.delenv(var, raising=False)
    # Point dotenv at an empty file so it never picks up a real .env on disk.
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("OSW_MCP_ENV_FILE", str(empty))
    config.reset()
    yield
    config.reset()


def _configure(monkeypatch, *, read_only: bool = False) -> None:
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "u")
    monkeypatch.setenv("OSW_PASSWORD", "p")
    monkeypatch.setenv("OSW_READ_ONLY", "true" if read_only else "false")
    config.reset()


def _tool_names(mcp) -> set[str]:
    tools = asyncio.run(mcp.list_tools())
    return {t.name for t in tools}


def test_every_mcp_surface_op_is_registered_and_no_others(monkeypatch):
    _configure(monkeypatch)

    names = _tool_names(server.create_server())

    expected = {op.name for op in iter_operations(surface="mcp", include_writes=True)}
    assert expected  # the comparison below must not pass vacuously
    assert names == expected


def test_jsondata_schema_unchanged_by_cli_typer_marker(monkeypatch):
    """A typer marker in a core signature must not alter the MCP JSON schema.

    ``create_or_update_entity``'s ``jsondata`` carries an
    ``Annotated[dict, typer.Option(parser=json_value)]`` marker so the CLI
    knows how to spell it. That only works because pydantic ignores
    Annotated metadata it does not recognise; if that ever stops holding,
    the schema shipped to a model silently changes.
    """
    _configure(monkeypatch)

    tools = asyncio.run(server.create_server().list_tools())
    tool = next(t for t in tools if t.name == "create_or_update_entity")

    assert tool.input_schema["properties"]["jsondata"]["type"] == "object"


def test_read_only_server_omits_writes_full_server_includes_them(monkeypatch):
    _configure(monkeypatch, read_only=True)
    names_read_only = _tool_names(server.create_server())

    _configure(monkeypatch, read_only=False)
    names_full = _tool_names(server.create_server())

    assert "get_entity" in names_read_only  # a reader survives read-only mode
    assert "create_or_update_entity" not in names_read_only
    assert "delete_entity" not in names_read_only
    assert "create_or_update_entity" in names_full
    assert "delete_entity" in names_full


def test_annotations_and_meta_reach_the_sdk_for_a_representative_op(monkeypatch):
    _configure(monkeypatch)

    tools = {t.name: t for t in asyncio.run(server.create_server().list_tools())}

    tool = tools["delete_entity"]
    assert tool.annotations is not None
    assert tool.annotations.destructive_hint is True
    assert tool.meta["anthropic/requiresUserInteraction"] is True
    assert "anthropic/maxResultSizeChars" in tool.meta


def test_no_instance_switching_tools_registered(monkeypatch):
    _configure(monkeypatch)

    names = _tool_names(server.create_server())

    # Assert something WAS registered first: the two absence checks below
    # would otherwise pass on an empty list.
    assert "get_entity" in names
    assert "list_instances" not in names
    assert "select_instance" not in names


def _write_cred_file(tmp_path, iris):
    cred_file = tmp_path / "accounts.yaml"
    cred_file.write_text(
        yaml.safe_dump({iri: {"username": "a", "password": "b"} for iri in iris}),
        encoding="utf-8",
    )
    return cred_file


def test_create_server_raises_when_no_domain_is_configured(monkeypatch, tmp_path):
    # A credential file with more than one iri makes settings valid (no
    # OSW_DOMAIN/OSW_USERNAME/OSW_PASSWORD required) but names no instance.
    cred_file = _write_cred_file(tmp_path, ["wiki-a.example.org", "wiki-b.example.org"])
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))
    config.reset()

    with pytest.raises(RuntimeError, match="No OSL instance configured"):
        server.create_server()


def test_create_server_does_not_auto_select_a_single_iri(monkeypatch, tmp_path):
    # config.get_active_domain() *would* resolve this one (the CLI relies on
    # that), but the server must not: which instance its tools reach has to be
    # readable from the configuration, not inferred from the credential file.
    cred_file = _write_cred_file(tmp_path, ["wiki-only.example.org"])
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))
    config.reset()
    assert config.get_active_domain() == "wiki-only.example.org"

    with pytest.raises(RuntimeError, match="No OSL instance configured"):
        server.create_server()


def test_build_server_is_quiet_by_default(monkeypatch, capsys):
    # The configuration source lines repeat what the MCP client's server entry
    # already says, so a successful start says nothing without OSW_VERBOSE.
    _configure(monkeypatch)

    server.create_server()

    assert "[osw]" not in capsys.readouterr().err


def test_build_server_writes_the_report_into_the_given_buffer(monkeypatch, capsys):
    _configure(monkeypatch)
    buf = io.StringIO()

    _mcp, ctx = server._build_server(buf)
    ctx.close()

    assert "[osw] credentials" in buf.getvalue()
    assert capsys.readouterr().err == ""


def test_main_prints_the_report_when_startup_fails(monkeypatch, tmp_path, capsys):
    # No OSW_DOMAIN: _build_server raises, and that is exactly when the
    # configuration sources have to be visible, OSW_VERBOSE or not.
    cred_file = _write_cred_file(tmp_path, ["wiki-a.example.org", "wiki-b.example.org"])
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))
    config.reset()

    with pytest.raises(SystemExit):
        server.main()

    err = capsys.readouterr().err
    assert "[osw] " in err
    assert "failed to start" in err
