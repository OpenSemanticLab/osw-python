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
import logging
import os
import platform
import sys
from contextlib import contextmanager

import pytest
import yaml

import osw
from osw.mcp import server
from osw.service import config
from osw.service.context import Context
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

    assert "[osw-mcp] credentials" in buf.getvalue()
    assert capsys.readouterr().err == ""


def test_build_server_report_lines_carry_the_mcp_prefix(monkeypatch):
    """The config source lines are shared code (osw.service.config); this
    server sets the "osw-mcp" prefix so they never show the CLI's "osw"."""
    _configure(monkeypatch)
    buf = io.StringIO()

    _mcp, ctx = server._build_server(buf)
    ctx.close()

    lines = buf.getvalue().splitlines()
    assert lines
    assert all(line.startswith("[osw-mcp]") for line in lines)


def _serve_without_blocking(monkeypatch) -> None:
    """Let main() return: no stdio loop, and no atexit handler left behind."""
    monkeypatch.setattr(server.MCPServer, "run", lambda self, **kwargs: None)
    monkeypatch.setattr(server.atexit, "register", lambda func: func)


# -- -h / -V / an unknown argument, all resolved before any credential is
# needed (Change: main() now takes argv and parses it with argparse) --------
def _refuse_to_build(*args, **kwargs):
    raise AssertionError("_build_server must not be called on this path")


def _expected_version_line(prog: str) -> str:
    """The line ``prog --version`` must print, built independently of
    ``server.version_line`` so a bug in that function (e.g. ignoring
    ``prog``) cannot pass these tests by comparing itself to itself."""
    location = os.path.dirname(osw.__file__)
    return (
        f"{prog} {osw.__version__} from {location} (Python {platform.python_version()})"
    )


def test_main_version_flag_prints_the_line_and_builds_no_server(monkeypatch, capsys):
    monkeypatch.setattr(server, "_build_server", _refuse_to_build)

    server.main(["--version"])

    out = capsys.readouterr().out.strip()
    assert out.startswith("osw-mcp ")
    assert out == _expected_version_line("osw-mcp")


def test_main_short_version_flag_prints_the_line_and_builds_no_server(
    monkeypatch, capsys
):
    monkeypatch.setattr(server, "_build_server", _refuse_to_build)

    server.main(["-V"])

    assert capsys.readouterr().out.strip() == _expected_version_line("osw-mcp")


def test_main_help_flag_exits_zero_with_the_help_on_stdout(monkeypatch, capsys):
    monkeypatch.setattr(server, "_build_server", _refuse_to_build)

    with pytest.raises(SystemExit) as exc_info:
        server.main(["-h"])

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "osw-mcp" in out
    assert "--version" in out


def test_main_with_no_argument_reads_sys_argv(monkeypatch, capsys):
    """``argv=None`` (the default) is argparse's own convention for "read
    the real command line", which ``ArgumentParser.parse_args`` implements by
    reading ``sys.argv[1:]`` itself, at call time. This proves that path
    actually works for ``main()``, not just that it forwards ``None``."""
    monkeypatch.setattr(sys, "argv", ["osw-mcp", "--version"])
    monkeypatch.setattr(server, "_build_server", _refuse_to_build)

    server.main()

    assert capsys.readouterr().out.strip() == _expected_version_line("osw-mcp")


_MCP_DOCS_URL = (
    "https://github.com/OpenSemanticLab/osw-python/blob/main/docs/tools/mcp.md."
)


@pytest.mark.parametrize("columns", ["60", "90", "132"])
def test_help_description_keeps_the_url_on_one_line(monkeypatch, columns):
    """argparse's default formatter wraps the description with textwrap,
    break_on_hyphens=True, so at some terminal widths (90 is one) a line ends
    with ".../osw-" and the next starts with "python/blob/...". The parser
    has to keep the URL intact regardless of the terminal width; COLUMNS is
    what shutil.get_terminal_size (which argparse's formatter uses) reads.
    """
    monkeypatch.setenv("COLUMNS", columns)

    lines = server._build_parser().format_help().splitlines()

    assert any(_MCP_DOCS_URL in line for line in lines)


def test_argparse_help_text_is_ascii():
    """osw-mcp's argparse help goes to stdout on the -h path, which main()
    does not force to UTF-8 (unlike the --version path). A non-ASCII
    character in the description or an option's help would risk
    UnicodeEncodeError on a locale that cannot represent it, the same class
    of defect tests/test_cli.py::test_every_help_string_is_ascii guards
    against for the typer app.
    """
    assert server._build_parser().format_help().isascii()


def test_main_rejects_an_unknown_argument(monkeypatch, capsys):
    monkeypatch.setattr(server, "_build_server", _refuse_to_build)

    with pytest.raises(SystemExit) as exc_info:
        server.main(["--bogus"])

    assert exc_info.value.code == 2
    assert "osw-mcp" in capsys.readouterr().err


def test_main_rejects_an_abbreviated_version_flag(monkeypatch, capsys):
    """argparse accepts an unambiguous abbreviation by default; osw's own
    CLI (click) does not, so osw-mcp turns that off (allow_abbrev=False) to
    match: an argument that is not exactly --version or -V is rejected."""
    monkeypatch.setattr(server, "_build_server", _refuse_to_build)

    with pytest.raises(SystemExit) as exc_info:
        server.main(["--vers"])

    assert exc_info.value.code == 2


def test_main_is_quiet_on_a_successful_start(monkeypatch, capsys):
    _configure(monkeypatch)
    _serve_without_blocking(monkeypatch)

    server.main([])

    assert "[osw]" not in capsys.readouterr().err


def test_main_prints_the_report_when_osw_verbose_is_set(monkeypatch, capsys):
    _configure(monkeypatch)
    monkeypatch.setenv("OSW_VERBOSE", "true")
    config.reset()
    _serve_without_blocking(monkeypatch)

    server.main([])

    err = capsys.readouterr().err
    assert "[osw-mcp] credentials" in err
    assert "[osw-mcp] env file" in err


def test_main_prints_the_report_when_startup_fails(monkeypatch, tmp_path, capsys):
    # No OSW_DOMAIN: _build_server raises, and that is exactly when the
    # configuration sources have to be visible, OSW_VERBOSE or not.
    cred_file = _write_cred_file(tmp_path, ["wiki-a.example.org", "wiki-b.example.org"])
    monkeypatch.setenv("OSW_MCP_CRED_FILEPATH", str(cred_file))
    config.reset()

    with pytest.raises(SystemExit):
        server.main([])

    err = capsys.readouterr().err
    assert "[osw-mcp] " in err
    assert "failed to start" in err


def test_main_forces_utf8_on_stderr_and_leaves_stdout_alone(monkeypatch):
    """An MCP client puts stderr on a pipe, so Python picks the locale encoding.

    The startup report carries the credential file path and the env file path
    (src/osw/service/config.py), so a directory or account name outside ASCII
    reaches the client's log mangled.

    stdout is left alone on purpose. The SDK's ``stdio_server`` re-wraps the
    binary buffer as UTF-8 itself and claims file descriptor 1 while doing it,
    so the JSON-RPC channel does not depend on this.
    """
    _configure(monkeypatch)
    _serve_without_blocking(monkeypatch)
    out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    err = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="backslashreplace")
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)

    server.main([])

    assert err.encoding == "utf-8"
    # reconfigure() resets errors to strict unless it is passed as well, and a
    # strict stderr would raise while reporting a failure.
    assert err.errors == "backslashreplace"
    assert out.encoding == "cp1252"


@contextmanager
def _osw_logging_on_the_captured_stream():
    """osw's own handler, writing to the stream pytest has in place right now.

    Two resets are needed. ``enable_logging`` resolves ``sys.stderr`` once,
    when it builds the handler (src/osw/__init__.py:149), so the handler
    attached when conftest imported osw still holds the stderr from before
    capsys replaced it. And that handler steps aside as soon as an ancestor
    logger has a handler of its own (src/osw/__init__.py:84-88), which
    pytest's log capture puts on the root logger.

    A context manager rather than a fixture, because pytest attaches those
    root handlers after the fixtures have run. Mirrors ``osw_logger`` and
    ``plain_logging`` in tests/test_logging_setup.py.
    """
    root, osw_logger = logging.getLogger(), logging.getLogger("osw")
    saved_root = root.handlers[:]
    saved = (osw_logger.handlers[:], osw_logger.level, osw._level_is_ours)
    root.handlers = []
    try:
        osw.enable_logging()
        yield
    finally:
        root.handlers = saved_root
        osw_logger.handlers, osw._level_is_ours = saved[0], saved[2]
        osw_logger.setLevel(saved[1])


def _no_connection(self, iri):
    raise RuntimeError("offline test: no connection is made")


def test_a_log_record_during_a_tool_call_never_reaches_stdout(
    monkeypatch, tmp_path, capsys
):
    """stdout is the JSON-RPC channel, so one log line there breaks the client.

    Two mechanisms keep it clean and only one of them is osw's own code:
    ``enable_logging`` defaults its handler to ``sys.stderr``, and the MCP SDK
    claims file descriptor 1 for the wire. A single edit to that default would
    undo the first, which is what this holds.

    The status operation is used because it logs a warning from inside
    ``ctx.guard()`` when the connection check fails
    (src/osw/service/ops/status.py:63). ``guard()`` rebinds ``sys.stdout`` to
    ``sys.stderr`` for the call's duration, and a handler built earlier does
    not follow that rebinding, so the record goes to the handler's own stream.
    That is the stream under test here.
    """
    _configure(monkeypatch)
    monkeypatch.setenv("OSW_STATE_DIR", str(tmp_path / "state"))
    # Makes the connection check fail without a network, which is what gets
    # status to log while the tool call is running.
    monkeypatch.setattr(Context, "osw_for", _no_connection)
    config.reset()
    mcp = server.create_server()

    with _osw_logging_on_the_captured_stream():
        asyncio.run(mcp.call_tool("status", {}))

    captured = capsys.readouterr()
    # First, so a run that emits no record at all fails here rather than
    # passing the stdout assertion without having observed anything.
    assert "status connection check failed" in captured.err
    assert captured.out == ""
