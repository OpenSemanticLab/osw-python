"""Unit tests for the osw CLI (src/osw/cli).

Runs in the plain dev env (no mcp extra needed): the CLI never imports the
mcp SDK. No network is touched -- ``osw.service.context.OswExpress`` is
patched wherever a test actually reaches a command's body.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
import typer
from typer.testing import CliRunner

import osw.cli.main as cli_main
from osw.cli.main import app
from osw.cli.render import render
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


# -- lazy Context -------------------------------------------------------------
def test_context_is_not_built_at_import_or_help_time(monkeypatch, runner):
    """Building the app / answering --help must never construct a Context."""
    calls = []
    orig_init = cli_main.Context.__init__

    def spy_init(self, *args, **kwargs):
        calls.append((args, kwargs))
        return orig_init(self, *args, **kwargs)

    monkeypatch.setattr(cli_main.Context, "__init__", spy_init)

    result = runner.invoke(app, ["entity", "get", "--help"])

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
    assert result.stderr.strip() == (
        "NotConfigured: SPARQL endpoint not configured. Set "
        "OSW_SPARQL_ENDPOINT or pass the 'endpoint' argument."
    )
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
    assert result.stderr.strip().startswith("ReadOnly:")
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
