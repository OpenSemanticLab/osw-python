"""Unit tests for the osw CLI (src/osw/cli).

The CLI never imports the mcp SDK, and no network is touched --
``osw.service.context.OswExpress`` is
patched wherever a test actually reaches a command's body.
"""

from __future__ import annotations

import io
import json
import logging
import os
import platform
import re
import sys
from unittest.mock import MagicMock

import click
import pytest
import typer
import yaml
from typer.testing import CliRunner

import osw
import osw.cli.main as cli_main
from osw.cli.main import app
from osw.cli.render import render
from osw.core import OverwriteOptions
from osw.service import config
from osw.service.params import json_value
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
    "OSW_VERBOSE",
    "OSW_MCP_VERBOSE",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    """No real credentials, no real .env file, no leaked active instance."""
    for var in _ALL_VARS:
        monkeypatch.delenv(var, raising=False)
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("OSW_ENV_FILE", str(empty))
    config.reset()
    yield
    config.reset()


@pytest.fixture
def configured_env(monkeypatch, tmp_path):
    """Just enough configuration for config.load(strict=False) to succeed."""
    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "u")
    monkeypatch.setenv("OSW_PASSWORD", "p")
    monkeypatch.setenv("OSW_STATE_DIR", str(tmp_path / "state"))
    config.reset()


@pytest.fixture
def runner():
    return CliRunner(mix_stderr=False)


def _error_lines(stderr: str) -> list[str]:
    """``stderr`` minus the ``[osw]`` configuration lines."""
    return [
        line for line in stderr.strip().splitlines() if not line.startswith("[osw] ")
    ]


_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_BOX = re.compile(r"[─-╿]")  # the Box Drawing block, rich's panel


def _usage_error(result) -> str:
    """``result``'s whole output as one line, without styling or box drawing.

    typer renders a usage error through rich, and two parts of that rendering
    depend on the environment. typer forces colour on when GITHUB_ACTIONS is
    set (typer/rich_utils.py), and rich wraps at the width of the real
    terminal. Colour breaks an option name into separate escape sequences,
    because rich styles the leading dash on its own, and wrapping breaks it
    across two lines. Either one defeats a plain substring check, which is why
    these assertions passed on a developer machine and failed in CI. Removing
    the escape sequences and the panel borders, then joining the lines, leaves
    the words the assertions are about.
    """
    text = _ANSI.sub("", result.stdout + result.stderr)
    return " ".join(_BOX.sub(" ", text).split())


def _banner_lines(stderr: str) -> list[str]:
    """The ``[osw]`` configuration lines of ``stderr``, in the order printed."""
    return [line for line in stderr.strip().splitlines() if line.startswith("[osw] ")]


def _fake_osw_with_page(exists=True):
    page = MagicMock()
    page.exists = exists
    fake_osw = MagicMock()
    fake_osw.site.get_page.return_value.pages = [page]
    return fake_osw, page


# -- help works with no configuration present --------------------------------
@pytest.mark.parametrize(
    "args",
    [["--help"], ["entity", "--help"], ["entity", "get", "--help"]],
)
def test_help_works_with_no_config_present(runner, args):
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stderr


# -- -h as an alias of --help (Change: issue #199) -----------------------------
@pytest.mark.parametrize(
    "args",
    [["-h"], ["entity", "-h"], ["entity", "get", "-h"]],
)
def test_short_help_flag_works_with_no_config_present(runner, args):
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stderr


@pytest.mark.parametrize(
    "args",
    [[], ["entity"], ["entity", "get"]],
)
def test_short_help_flag_prints_the_same_help_as_the_long_form(runner, args):
    """-h has to work on the root, on a subgroup and on a leaf command,
    each printing that same command's own help."""
    long_result = runner.invoke(app, [*args, "--help"])
    short_result = runner.invoke(app, [*args, "-h"])

    assert short_result.exit_code == 0, short_result.stderr
    assert _usage_error(short_result) == _usage_error(long_result)


# -- --version / -V (Change: issue #199) ----------------------------------------
def _expected_version_line(prog: str) -> str:
    """The line ``prog --version`` must print, built independently of
    ``cli_main.version_line`` so a bug in that function (e.g. ignoring
    ``prog``) cannot pass these tests by comparing itself to itself."""
    location = os.path.dirname(osw.__file__)
    return (
        f"{prog} {osw.__version__} from {location} (Python {platform.python_version()})"
    )


@pytest.fixture
def _no_osw_env(monkeypatch, tmp_path):
    """No OSW_* variable at all, not even one _ALL_VARS/``_clean_env`` does
    not happen to list, and no .env file discoverable by searching upward
    from the working directory. --version must work with neither, unlike
    every other command, which is what this isolates for."""
    for key in list(os.environ):
        if key.startswith("OSW_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)


def test_version_flag_prints_one_line_matching_the_format(runner, _no_osw_env):
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0, result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("osw ")
    assert lines[0] == _expected_version_line("osw")


def test_short_version_flag_prints_the_same_line(runner, _no_osw_env):
    result = runner.invoke(app, ["-V"])

    assert result.exit_code == 0, result.stderr
    assert result.stdout.splitlines() == [_expected_version_line("osw")]


def test_version_callback_forces_stdout_to_utf8_before_printing(monkeypatch):
    """The eager --version callback runs before ``_callback``'s own body, so
    ``_force_utf8_output`` never covers it (see that function's docstring).
    The line it prints names the package's install directory, which can
    contain a character the locale encoding lacks, so it has to force UTF-8
    itself -- the same reason ``osw-mcp -V`` already does
    (``osw.mcp.server.main``).
    """
    out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", out)
    line = "osw 1.0 from C:\\Users\\Ren\u0151 (Python 3.12.7)"  # \u0151 has no cp1252 code point
    monkeypatch.setattr(cli_main, "version_line", lambda prog: line)

    with pytest.raises(typer.Exit):
        cli_main._version_callback(True)

    out.flush()
    # echo() appends "\n", which an io.TextIOWrapper with the default
    # newline=None translates to os.linesep on write (e.g. "\r\n" on Windows).
    assert out.buffer.getvalue().decode("utf-8").rstrip("\r\n") == line


# -- lazy Context -------------------------------------------------------------
@pytest.mark.parametrize(
    "cli_args",
    [["entity", "get", "--help"], ["--version"]],
    ids=["--help", "--version"],
)
def test_context_is_not_built_at_import_or_help_time(monkeypatch, runner, cli_args):
    """Building the app / answering --help / --version must never construct
    a Context."""
    calls = []
    orig_init = cli_main.Context.__init__

    def spy_init(self, *args, **kwargs):
        calls.append((args, kwargs))
        return orig_init(self, *args, **kwargs)

    monkeypatch.setattr(cli_main.Context, "__init__", spy_init)

    result = runner.invoke(app, cli_args)

    assert result.exit_code == 0
    assert calls == []


# -- command tree ---------------------------------------------------------------
def test_every_cli_operation_is_registered_at_its_expected_path():
    click_app = typer.main.get_command(app)
    for op in iter_operations(surface="cli"):
        if op.group is None:
            assert op.command in click_app.commands, op.command
        else:
            assert op.group in click_app.commands, op.group
            group_cmd = click_app.commands[op.group]
            assert op.command in group_cmd.commands, (op.group, op.command)


# -- successful command / rendering --------------------------------------------
def test_successful_command_renders_to_stdout(runner, configured_env, monkeypatch):
    fake_osw, page = _fake_osw_with_page()
    page.get_slot_content.return_value = {"label": [{"text": "X"}]}
    page.get_url.return_value = "https://wiki.example.org/wiki/Item:OSW1"
    monkeypatch.setattr("osw.service.context.OswExpress", lambda **kwargs: fake_osw)

    result = runner.invoke(app, ["entity", "get", "Item:OSW1"])

    assert result.exit_code == 0, result.stderr
    assert "Item:OSW1" in result.stdout
    assert "exists" in result.stdout


def test_json_flag_emits_parseable_json(runner, configured_env, monkeypatch):
    fake_osw, page = _fake_osw_with_page()
    page.get_slot_content.return_value = {"label": [{"text": "X"}]}
    page.get_url.return_value = "https://wiki.example.org/wiki/Item:OSW1"
    monkeypatch.setattr("osw.service.context.OswExpress", lambda **kwargs: fake_osw)

    result = runner.invoke(app, ["--json", "entity", "get", "Item:OSW1"])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "title": "Item:OSW1",
        "exists": True,
        "jsondata": {"label": [{"text": "X"}]},
        "url": "https://wiki.example.org/wiki/Item:OSW1",
        "truncated": False,
    }


# -- OpError exit codes / clean error output ------------------------------------
def test_op_error_exits_with_its_exit_code_and_no_traceback(runner, configured_env):
    result = runner.invoke(app, ["search", "sparql", "SELECT * WHERE {?s ?p ?o}"])

    assert result.exit_code == 5
    assert _error_lines(result.stderr) == [
        "NotConfigured: SPARQL endpoint not configured. Set "
        "OSW_SPARQL_ENDPOINT or pass the 'endpoint' argument."
    ]
    assert "Traceback" not in result.stderr
    assert "Traceback" not in result.stdout


# -- --read-only ----------------------------------------------------------------
def test_read_only_blocks_a_write_command(runner, configured_env):
    result = runner.invoke(
        app,
        [
            "--read-only",
            "entity",
            "put",
            "Category:Item",
            "--jsondata",
            '{"label": [{"text": "x"}]}',
        ],
    )

    assert result.exit_code == 4
    assert _error_lines(result.stderr)[0].startswith("ReadOnly:")
    assert "Traceback" not in result.stderr


# -- set_slot's slot-dependent content coercion ---------------------------------
# `content` is typed Union[str, dict, list] in the core and typer cannot express
# a Union, so osw.cli.main coerces it after both arguments are known, consulting
# the sibling `slot` argument's content model. Both directions matter: a JSON
# slot given a raw string fails with InvalidContent, and a wikitext slot must not
# have "123" silently parsed into an int.
def test_set_slot_parses_content_for_a_json_slot(runner, configured_env, monkeypatch):
    fake_osw, page = _fake_osw_with_page()
    monkeypatch.setattr("osw.service.context.OswExpress", lambda **kwargs: fake_osw)

    result = runner.invoke(app, ["slot", "set", "Item:OSW1", "jsondata", '{"a": 1}'])

    assert result.exit_code == 0, result.stderr
    page.set_slot_content.assert_called_once_with("jsondata", {"a": 1})


def test_set_slot_leaves_wikitext_content_a_string(runner, configured_env, monkeypatch):
    fake_osw, page = _fake_osw_with_page()
    monkeypatch.setattr("osw.service.context.OswExpress", lambda **kwargs: fake_osw)

    result = runner.invoke(app, ["slot", "set", "Item:OSW1", "main", "123"])

    assert result.exit_code == 0, result.stderr
    page.set_slot_content.assert_called_once_with("main", "123")


# -- json_value -----------------------------------------------------------------
def test_json_value_parses_a_literal():
    assert json_value('{"a": 1}') == {"a": 1}


def test_json_value_reads_a_file(tmp_path):
    path = tmp_path / "data.json"
    path.write_text('{"a": 1}', encoding="utf-8")
    assert json_value(f"@{path}") == {"a": 1}


def test_json_value_rejects_malformed_json():
    with pytest.raises(typer.BadParameter):
        json_value("not-json")


# -- render -----------------------------------------------------------------
def test_render_json_is_parseable():
    result = {"a": 1, "b": [1, 2]}
    assert json.loads(render(result, as_json=True)) == result


def test_render_title_list_prints_titles_and_footer():
    result = {"titles": ["Item:OSW1", "Item:OSW2"], "count": 2, "truncated": False}
    rendered = render(result, as_json=False)
    lines = rendered.splitlines()
    assert lines[0] == "Item:OSW1"
    assert lines[1] == "Item:OSW2"
    assert "2" in lines[2]


def test_render_dict_shows_key_value_lines():
    result = {"title": "Item:OSW1", "exists": True}
    rendered = render(result, as_json=False)
    assert "title" in rendered
    assert "Item:OSW1" in rendered
    assert "exists" in rendered


# -- output encoding ------------------------------------------------------------
# Redirected stdout on Windows is opened with the locale encoding, not UTF-8, so
# a German label used to reach the consumer as cp1252 bytes. CliRunner's charset
# gives the captured stream that same encoding, which reproduces the platform
# behaviour everywhere, so these run on Linux CI too.
_MISSING = object()  # "do not set this attribute at all", distinct from None


@pytest.fixture
def cp1252_runner():
    return CliRunner(mix_stderr=False, charset="cp1252")


def _fake_osw_labelled(monkeypatch, label: str):
    """Patch in an entity whose label slot holds ``label``."""
    fake_osw, page = _fake_osw_with_page()
    page.get_slot_content.return_value = {"label": [{"text": label}]}
    page.get_url.return_value = "https://wiki.example.org/wiki/Item:OSW1"
    monkeypatch.setattr("osw.service.context.OswExpress", lambda **kwargs: fake_osw)


def test_json_output_is_utf8_when_stdout_uses_the_locale_encoding(
    cp1252_runner, configured_env, monkeypatch
):
    _fake_osw_labelled(monkeypatch, "Änderungen")

    result = cp1252_runner.invoke(app, ["--json", "entity", "get", "Item:OSW1"])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout_bytes.decode("utf-8"))
    assert payload["jsondata"]["label"][0]["text"] == "Änderungen"


def test_human_output_is_utf8_when_stdout_uses_the_locale_encoding(
    cp1252_runner, configured_env, monkeypatch
):
    _fake_osw_labelled(monkeypatch, "Änderungen")

    result = cp1252_runner.invoke(app, ["entity", "get", "Item:OSW1"])

    assert result.exit_code == 0, result.stderr
    assert "Änderungen" in result.stdout_bytes.decode("utf-8")


def test_error_message_is_utf8_when_stderr_uses_the_locale_encoding(
    cp1252_runner, configured_env, monkeypatch
):
    """An error names the page it failed on, so stderr carries labels too."""
    fake_osw, _page = _fake_osw_with_page(exists=False)
    fake_osw.load_entity.return_value.entities = []
    monkeypatch.setattr("osw.service.context.OswExpress", lambda **kwargs: fake_osw)

    result = cp1252_runner.invoke(app, ["--json", "entity", "export", "Item:Änderung"])

    assert result.exit_code == 2
    assert "Item:Änderung" in result.stderr_bytes.decode("utf-8")


def test_forcing_utf8_keeps_the_error_handler_each_stream_was_given(monkeypatch):
    """``reconfigure`` resets ``errors`` to strict unless it is passed as well.

    Python gives stderr ``backslashreplace`` precisely so that reporting a
    failure cannot itself raise. Switching the encoding must not drop that.
    """
    err = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="backslashreplace")
    monkeypatch.setattr(sys, "stderr", err)
    monkeypatch.setattr(
        sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    )

    cli_main._force_utf8_output()

    assert err.encoding == "utf-8"
    err.write("\udc80")  # a lone surrogate, which "strict" refuses to encode
    err.flush()
    assert err.buffer.getvalue() == rb"\udc80"


def test_every_help_string_is_ascii():
    """Guards the one gap ``_force_utf8_output`` cannot close.

    Click prints help and rejects an unknown name before any callback runs,
    so those paths keep the locale encoding. --version / -V also prints
    before that callback (its own callback is eager, like --help), but it
    forces UTF-8 on stdout itself (see ``cli_main._version_callback``), so it
    is not part of this gap and is exempt here. For everything else, this is
    only harmless while no help string contains a character the locale
    encoding may lack. Adding a German option description would make it a
    real defect, and this test is what reports it.
    """
    offenders = []

    def walk(command, path):
        texts = {"help": command.help, "short_help": command.short_help}
        for param in command.params:
            texts[f"--{param.name}"] = getattr(param, "help", None)
        for where, text in texts.items():
            if text and not text.isascii():
                offenders.append(f"{' '.join(path) or 'osw'} {where}: {text!r}")
        for name, sub in getattr(command, "commands", {}).items():
            walk(sub, [*path, name])

    walk(typer.main.get_command(app), [])

    assert offenders == []


def test_a_substituted_stream_with_no_usable_errors_value_is_left_alone(monkeypatch):
    """Both halves of the guard are needed, not just the ``reconfigure`` half.

    A host application may put an object that is not a ``TextIOWrapper`` on
    ``sys.stdout``. Reading ``.errors`` on one that lacks it raises, which
    would end the command. A ``.errors`` of ``None`` is no better: passing it
    on means ``strict``, the handler this function exists to preserve.
    """

    class Substituted:
        def __init__(self, errors):
            self.calls = []
            if errors is not _MISSING:
                self.errors = errors

        def reconfigure(self, **kwargs):
            self.calls.append(kwargs)

    without = Substituted(_MISSING)
    none_valued = Substituted(None)
    monkeypatch.setattr(sys, "stdout", without)
    monkeypatch.setattr(sys, "stderr", none_valued)

    cli_main._force_utf8_output()

    assert without.calls == []
    assert none_valued.calls == []


def test_a_log_handler_holding_stderr_writes_utf8_after_the_switch(monkeypatch):
    """osw logs to ``sys.stderr``, and its handler is built at import time.

    ``logging.StreamHandler`` stores the stream object it was given, so the
    handler osw attaches in ``enable_logging`` holds ``sys.stderr`` itself.
    ``reconfigure`` changes that object in place rather than replacing it,
    which is why an already attached handler writes UTF-8 too. Replacing
    ``sys.stderr`` with a new object would leave the handler on the old one.
    """
    err = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="backslashreplace")
    monkeypatch.setattr(sys, "stderr", err)
    handler = logging.StreamHandler(sys.stderr)  # as osw.enable_logging does
    logger = logging.getLogger("test_utf8_handler")
    logger.addHandler(handler)
    monkeypatch.setattr(
        sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    )

    cli_main._force_utf8_output()
    logger.warning("Änderungen")
    handler.flush()

    assert handler.stream is err
    assert "Änderungen" in err.buffer.getvalue().decode("utf-8")


def test_label_the_locale_encoding_cannot_represent_is_written_not_raised(
    cp1252_runner, configured_env, monkeypatch
):
    """cp1252 has no Japanese characters, so encoding used to raise, not corrupt."""
    _fake_osw_labelled(monkeypatch, "文字")

    result = cp1252_runner.invoke(app, ["--json", "entity", "get", "Item:OSW1"])

    assert result.exit_code == 0, result.exception or result.stderr
    payload = json.loads(result.stdout_bytes.decode("utf-8"))
    assert payload["jsondata"]["label"][0]["text"] == "文字"


# -- CLI-only path-taking file commands (osw.cli.ops) ---------------------------
# These are the only operations in the codebase allowed to name a path; they
# are exercised here rather than in tests/test_service_ops_files.py.
def test_download_file_writes_to_tmp_path(
    runner, configured_env, monkeypatch, tmp_path
):
    fake_osw, _page = _fake_osw_with_page(exists=True)
    monkeypatch.setattr("osw.service.context.OswExpress", lambda **kwargs: fake_osw)

    wf = MagicMock()
    wf.title = "OSWabc123.txt"
    wf.get.return_value = io.BytesIO(b"hello world")
    monkeypatch.setattr("osw.cli.ops.WikiFileController", MagicMock(return_value=wf))

    result = runner.invoke(
        app,
        ["file", "download", "File:OSWabc123.txt", "--target-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.stderr
    written = tmp_path / "OSWabc123.txt"
    assert written.read_bytes() == b"hello world"


def test_download_file_missing_page_raises_not_found(
    runner, configured_env, monkeypatch, tmp_path
):
    fake_osw, _page = _fake_osw_with_page(exists=False)
    monkeypatch.setattr("osw.service.context.OswExpress", lambda **kwargs: fake_osw)

    result = runner.invoke(
        app,
        ["file", "download", "File:doesnotexist.txt", "--target-dir", str(tmp_path)],
    )

    assert result.exit_code == 2  # NotFound
    assert "NotFound" in result.stderr


def test_upload_file_reads_from_tmp_path(runner, configured_env, monkeypatch, tmp_path):
    fake_osw, _page = _fake_osw_with_page(exists=True)
    monkeypatch.setattr("osw.service.context.OswExpress", lambda **kwargs: fake_osw)

    src = tmp_path / "photo.png"
    src.write_bytes(b"binarydata")

    wf = MagicMock()
    wf.namespace = "File"
    wf.title = "OSWxyz.png"
    wf.url = "https://wiki.example.org/wiki/File:OSWxyz.png"
    monkeypatch.setattr("osw.cli.ops.WikiFileController", MagicMock(return_value=wf))
    captured = {}
    wf.put.side_effect = lambda stream, **kwargs: captured.update(
        name=stream.name, content=stream.read(), kwargs=kwargs
    )

    result = runner.invoke(app, ["file", "upload", str(src)])

    assert result.exit_code == 0, result.stderr
    wf.put.assert_called_once()
    assert captured["name"] == "photo.png"
    assert captured["content"] == b"binarydata"
    assert captured["kwargs"] == {"overwrite": OverwriteOptions.true}


def test_upload_file_honors_name_and_no_overwrite(
    runner, configured_env, monkeypatch, tmp_path
):
    fake_osw, _page = _fake_osw_with_page(exists=True)
    monkeypatch.setattr("osw.service.context.OswExpress", lambda **kwargs: fake_osw)

    src = tmp_path / "photo.png"
    src.write_bytes(b"binarydata")

    wf = MagicMock()
    wf.namespace = "File"
    wf.title = "OSWxyz.png"
    wf.url = "https://wiki.example.org/wiki/File:OSWxyz.png"
    monkeypatch.setattr("osw.cli.ops.WikiFileController", MagicMock(return_value=wf))
    captured = {}
    wf.put.side_effect = lambda stream, **kwargs: captured.update(
        name=stream.name, kwargs=kwargs
    )

    result = runner.invoke(
        app,
        ["file", "upload", str(src), "--name", "renamed.png", "--no-overwrite"],
    )

    assert result.exit_code == 0, result.stderr
    assert captured["name"] == "renamed.png"
    assert captured["kwargs"] == {"overwrite": OverwriteOptions.false}


def test_upload_file_missing_source_raises_not_found(runner, configured_env, tmp_path):
    result = runner.invoke(app, ["file", "upload", str(tmp_path / "nope.png")])

    assert result.exit_code == 2  # NotFound
    assert "NotFound" in result.stderr


# -- ledger path ------------------------------------------------------------------
def test_ledger_path_prints_the_ledger_file_path(runner, configured_env):
    result = runner.invoke(app, ["ledger", "path"])

    assert result.exit_code == 0, result.stderr
    assert "path" in result.stdout


# -- instances list / --instance ---------------------------------------------------
def test_instance_list_never_leaks_credentials(runner, monkeypatch, tmp_path):
    cred_file = tmp_path / "accounts.yaml"
    cred_file.write_text(
        yaml.safe_dump({
            "wiki-a.example.org": {"username": "alice", "password": "supersecret"},
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("OSW_CRED_FILEPATH", str(cred_file))
    config.reset()

    result = runner.invoke(app, ["instances", "list"])

    assert result.exit_code == 0, result.stderr
    assert "wiki-a.example.org" in result.stdout
    assert "supersecret" not in result.stdout
    assert "alice" not in result.stdout


def test_instance_flag_sets_active_instance(runner, monkeypatch, tmp_path):
    cred_file = tmp_path / "accounts.yaml"
    cred_file.write_text(
        yaml.safe_dump({
            "wiki-a.example.org": {"username": "a", "password": "b"},
            "wiki-b.example.org": {"username": "c", "password": "d"},
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("OSW_CRED_FILEPATH", str(cred_file))
    config.reset()

    result = runner.invoke(
        app, ["--instance", "wiki-b.example.org", "--json", "instances", "list"]
    )

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["active_iri"] == "wiki-b.example.org"
    assert payload["active_domain"] == "wiki-b.example.org"


def test_instance_flag_unknown_iri_exits_cleanly(runner, monkeypatch, tmp_path):
    cred_file = tmp_path / "accounts.yaml"
    cred_file.write_text(
        yaml.safe_dump({"wiki-a.example.org": {"username": "a", "password": "b"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OSW_CRED_FILEPATH", str(cred_file))
    config.reset()

    result = runner.invoke(app, ["--instance", "nope.example.org", "instances", "list"])

    assert result.exit_code == 3  # UnknownInstance
    assert _error_lines(result.stderr)[0].startswith("UnknownInstance:")
    assert "wiki-a.example.org" in result.stderr
    assert "Traceback" not in result.stderr


def test_successful_command_reports_only_the_credential_source(
    runner, configured_env, monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)  # no accounts.pwd.yaml to discover

    result = runner.invoke(app, ["instances", "list"])

    assert result.exit_code == 0, result.stderr
    lines = _banner_lines(result.stderr)
    assert len(lines) == 1
    assert lines[0].startswith("[osw] credentials    :")


def test_verbose_adds_the_env_file_line(runner, configured_env, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["--verbose", "instances", "list"])

    assert result.exit_code == 0, result.stderr
    lines = _banner_lines(result.stderr)
    assert len(lines) == 2
    assert lines[0].startswith("[osw] credentials    :")
    assert lines[1].startswith("[osw] env file       :")


def test_failing_command_reports_every_source_without_verbose(
    runner, monkeypatch, tmp_path
):
    # No credentials at all, so the command fails inside the operation.
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["instances", "list"])

    assert result.exit_code == 1
    lines = _banner_lines(result.stderr)
    assert len(lines) == 2
    assert lines[0].startswith("[osw] credentials    :")
    assert lines[1].startswith("[osw] env file       :")
    # The stdio-hang rationale belongs to the MCP server, not to the CLI.
    assert "stdio transport" not in result.stderr


# -- status reports a credential-file username too (regression, Change 2) -------
def test_status_reports_username_from_credential_file(runner, monkeypatch, tmp_path):
    """settings.redacted() only sees OSW_USERNAME/OSL_USERNAME; a username
    configured only via a credential file must still show up in status."""
    cred_file = tmp_path / "accounts.yaml"
    cred_file.write_text(
        yaml.safe_dump({
            "wiki-a.example.org": {"username": "alice", "password": "supersecret"},
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("OSW_CRED_FILEPATH", str(cred_file))
    config.reset()
    monkeypatch.setattr("osw.service.context.OswExpress", lambda **kwargs: MagicMock())

    result = runner.invoke(app, ["--json", "status"])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["username"] == "alice"
    assert "supersecret" not in result.stdout


def test_status_username_matches_the_one_the_login_uses(runner, monkeypatch, tmp_path):
    """With both sources configured, report the one the connection will use.

    CredentialManager.get_credential consults the credential file first and
    only falls back to OSW_USERNAME, so status must do the same. Reporting the
    environment name here would name an account the session does not log in as.
    """
    cred_file = tmp_path / "accounts.yaml"
    cred_file.write_text(
        yaml.safe_dump({
            "wiki-a.example.org": {"username": "from-file", "password": "secret"},
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("OSW_CRED_FILEPATH", str(cred_file))
    monkeypatch.setenv("OSW_USERNAME", "from-env")
    monkeypatch.setenv("OSW_PASSWORD", "env-secret")
    monkeypatch.setenv("OSW_DOMAIN", "wiki-a.example.org")
    config.reset()
    monkeypatch.setattr("osw.service.context.OswExpress", lambda **kwargs: MagicMock())

    result = runner.invoke(app, ["--json", "status"])

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["username"] == "from-file"


# -- adapter-carried log prefix (Change: shared code no longer hardcodes it) ----
def test_shared_code_reports_the_cli_prefix_on_a_connection_failure(
    runner, configured_env, monkeypatch, caplog
):
    """status's connection-failure branch lives in shared code
    (osw.service.ops.status), so it must carry whichever prefix the running
    adapter set, not a hardcoded one; the CLI sets "osw"."""
    # Start from a foreign prefix so the assertion below proves the CLI's own
    # callback set "osw"; starting from the config default would still pass
    # even if that callback's set_log_prefix call were removed.
    config.set_log_prefix("osw-mcp")

    def _boom(**kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr("osw.service.context.OswExpress", _boom)

    # the failure is logged, not printed: CliRunner captures sys.stderr, but
    # under pytest the record propagates to pytest's own handler instead.
    with caplog.at_level(logging.WARNING, logger="osw"):
        result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, result.stderr
    assert "[osw] status connection check failed" in caplog.text
    assert "[osw-mcp]" not in caplog.text


# -- instances status --------------------------------------------------------------
def test_instances_status_reports_each_configured_instance(
    runner, monkeypatch, tmp_path
):
    cred_file = tmp_path / "accounts.yaml"
    cred_file.write_text(
        yaml.safe_dump({
            "wiki-a.example.org": {"username": "alice", "password": "secreta"},
            "wiki-b.example.org": {"username": "bob", "password": "secretb"},
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("OSW_CRED_FILEPATH", str(cred_file))
    config.reset()
    monkeypatch.setattr("osw.service.context.OswExpress", lambda **kwargs: MagicMock())

    result = runner.invoke(app, ["--json", "instances", "status"])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    by_iri = {entry["iri"]: entry for entry in payload["instances"]}
    assert set(by_iri) == {"wiki-a.example.org", "wiki-b.example.org"}
    assert by_iri["wiki-a.example.org"]["username"] == "alice"
    assert by_iri["wiki-b.example.org"]["username"] == "bob"
    assert by_iri["wiki-a.example.org"]["connected"] is True
    assert by_iri["wiki-b.example.org"]["connected"] is True
    assert "secreta" not in result.stdout
    assert "secretb" not in result.stdout


def test_instances_status_reports_a_failing_instance_without_stopping(
    runner, monkeypatch, tmp_path
):
    cred_file = tmp_path / "accounts.yaml"
    cred_file.write_text(
        yaml.safe_dump({
            "wiki-a.example.org": {"username": "alice", "password": "secreta"},
            "wiki-b.example.org": {"username": "bob", "password": "secretb"},
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("OSW_CRED_FILEPATH", str(cred_file))
    config.reset()

    def fake_osw_express(*, domain, **kwargs):
        if domain == "wiki-a.example.org":
            raise RuntimeError("connection refused")
        return MagicMock()

    monkeypatch.setattr("osw.service.context.OswExpress", fake_osw_express)

    result = runner.invoke(app, ["--json", "instances", "status"])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    by_iri = {entry["iri"]: entry for entry in payload["instances"]}
    assert by_iri["wiki-a.example.org"]["connected"] is False
    assert "error" in by_iri["wiki-a.example.org"]
    assert by_iri["wiki-b.example.org"]["connected"] is True
    assert "error" not in by_iri["wiki-b.example.org"]


# -- a root option typed after the command names the correct form (Change 5) ----
def test_root_option_after_command_names_the_correct_form(runner):
    result = runner.invoke(app, ["status", "--instance", "wiki-dev.example.org"])

    assert result.exit_code != 0
    combined = _usage_error(result)
    assert "--instance <iri>" in combined
    assert "before the command" in combined


def test_root_option_after_grouped_command_names_the_correct_form(runner):
    result = runner.invoke(app, ["entity", "--instance", "x", "get", "T"])

    assert result.exit_code != 0
    combined = _usage_error(result)
    assert "--instance <iri>" in combined
    assert "before the command" in combined


@pytest.mark.parametrize("flag", ["--version", "-V"])
def test_version_option_after_grouped_command_names_the_correct_form(runner, flag):
    """--version and -V (Change: issue #199) belong in _ROOT_OPTIONS too."""
    result = runner.invoke(app, ["entity", flag])

    assert result.exit_code != 0
    combined = _usage_error(result)
    assert flag in combined
    assert "before the command" in combined


def test_unknown_subcommand_option_names_help_with_the_configured_order(runner):
    """help_option_names is ``["--help", "-h"]`` (Change: issue #199), and
    click builds its "Try '...' for help." hint from ``help_option_names[0]``,
    so an ordinary usage error -- one _root_option_hint leaves untouched,
    unlike --instance/--version above -- must still name --help, not -h.
    CliRunner.invoke uses "root" as the program name in this hint, not "osw",
    so the assertion checks the part after it rather than the whole line."""
    result = runner.invoke(app, ["entity", "--no-such-option"])

    assert result.exit_code != 0
    combined = _usage_error(result)
    assert "entity --help' for help." in combined
    assert "entity -h' for help." not in combined


def test_root_options_mapping_covers_every_root_option():
    """_ROOT_OPTIONS is maintained by hand, next to but apart from _callback.

    Without this check, adding or renaming a root option would silently stop
    the hint from firing for it, and the user would be back to click's bare
    "No such option".
    """
    root = typer.main.get_command(app)
    declared = {
        opt
        for param in root.params
        if isinstance(param, click.Option)
        for opt in [*param.opts, *param.secondary_opts]
        if opt not in ("--help", "-h")
    }

    assert declared == set(cli_main._ROOT_OPTIONS)


def test_misspelled_command_option_keeps_clicks_suggestion(runner):
    """--json is a root option, but here it is a misspelling of --jsondata.

    The hint must not displace click's "Did you mean", which names the option
    the user actually wanted.
    """
    result = runner.invoke(app, ["entity", "put", "--json", "{}"])

    assert result.exit_code != 0
    combined = _usage_error(result)
    assert "--jsondata" in combined
    assert "before the command" not in combined
