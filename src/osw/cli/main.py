"""Entry point for the ``osw`` CLI.

Run via the ``osw`` console script or ``python -m osw.cli.main``. The command
tree is assembled once, at import time, by looping over
:func:`osw.service.registry.iter_operations`; building it never touches
credentials or the network. The :class:`~osw.service.context.Context` for a
given invocation is built lazily, inside each command's callback, so
``osw --help`` (and friends) work with no configuration present at all.
"""

from __future__ import annotations

import inspect
import sys
from typing import Any, Optional, get_type_hints

import click
import typer
from typer.core import TyperCommand, TyperGroup

# Registers the CLI-only, path-taking operations (file download/upload, ledger
# path). Imported here -- and nowhere in osw.mcp -- so a path-taking operation
# can never reach the MCP registry.
import osw.cli.ops

# Registers every operation in osw.service.registry.REGISTRY as a side effect.
import osw.service.ops  # noqa: F401
from osw.service import config, errors
from osw.service.context import Context, Policy
from osw.service.errors import OpError
from osw.service.params import json_value
from osw.service.registry import Operation, bind, iter_operations
from osw.wtsite import SLOTS

from .render import render

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _force_utf8_output() -> None:
    """Encode stdout and stderr as UTF-8, whatever the locale asks for.

    Python encodes a redirected stream with the locale encoding, which on a
    German Windows system is cp1252. A non-ASCII label then reaches the
    consumer as bytes no JSON parser can read, and a character cp1252 has no
    code point for -- Japanese, Greek, Cyrillic -- raises UnicodeEncodeError
    and ends the command. A Windows console stream is UTF-8 already, so on
    Windows only redirected output changes. Elsewhere a terminal uses the
    locale encoding, so this overrides a deliberate non-UTF-8 LANG or
    PYTHONIOENCODING too. stderr is covered as well as stdout, because
    ``Context.guard`` sends captured stdout to stderr under ``--json``.

    Called from the app callback, so it covers every command. Click prints
    help and rejects an unknown root-level name before any callback runs, so
    those paths keep the locale encoding. They carry no wiki content: every
    help string in this package is ASCII (held by a test), and rich
    substitutes its box-drawing characters once the stream is not UTF-8. What
    stays exposed is the name the user typed, echoed back in a usage error --
    an unknown command name or an unknown root option name. A name typed
    after the command is fine, because click resolves the command, runs this
    callback, and only then parses the command's own arguments.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        errors = getattr(stream, "errors", None)
        # A stream a test harness or host application substituted may have
        # neither, and then decides its own encoding. Both are required:
        # errors= must be passed, because reconfigure() silently resets the
        # handler to strict otherwise, which would let stderr raise while
        # reporting a failure. Passing errors=None does exactly that too.
        if reconfigure is not None and errors is not None:
            reconfigure(encoding="utf-8", errors=errors)


@app.callback()
def _callback(
    ctx: typer.Context,
    instance: Optional[str] = typer.Option(
        None,
        "--instance",
        help="Iri of the OSL instance to use for this command, when more "
        "than one is configured (e.g. via a credential file).",
    ),
    as_json: bool = typer.Option(
        False, "--json", "-j", help="Emit machine-readable JSON on stdout."
    ),
    read_only: bool = typer.Option(
        False, "--read-only", help="Refuse write operations."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show full tracebacks on unexpected errors."
    ),
) -> None:
    """osw: command-line access to an OpenSemanticLab (OSW) instance.

    Connection settings and credentials come from the environment or a
    .env file (see ``osw.service.config``). Pass --instance to pick which
    configured instance this invocation talks to; unlike the MCP server, the
    CLI is stateless, so the choice only applies to this one command.
    """
    # Set first, before a call that can raise: set_log_prefix never raises, so
    # the prefix is always correct for any message printed on the way out,
    # including one printed while handling set_env_file_discovery's error.
    config.set_log_prefix("osw")
    # Before any output, including the configuration banner.
    _force_utf8_output()
    # The CLI's working directory is the one the user typed the command in, so
    # searching it upward for a .env is what they mean. The MCP server leaves
    # this off: its working directory is chosen by the MCP client.
    config.set_env_file_discovery(True)
    ctx.obj = {
        "instance": instance,
        "as_json": as_json,
        "read_only": read_only,
        "verbose": verbose,
    }


# These belong to ``osw`` itself (the root callback above) and, like git and
# docker, must come before the command name; typer/click reject them after
# it. The mapping and the classes below turn that rejection into a message
# that names the correct form instead of a bare "No such option".
_ROOT_OPTIONS = {
    "--instance": "--instance <iri>",
    "--json": "--json",
    "-j": "-j",
    "--read-only": "--read-only",
    "--verbose": "--verbose",
    "-v": "-v",
}


def _root_option_hint(ctx, exc):
    """Turn a root option typed after the command into an actionable error.

    Returns ``exc`` unchanged when it does not name one of ``_ROOT_OPTIONS``,
    and also when click already found a close match on the command itself:
    ``osw entity put --json ...`` is a misspelling of that command's own
    ``--jsondata``, and click's "Did you mean" is the better message there.
    """
    usage = _ROOT_OPTIONS.get(exc.option_name)
    if usage is None or exc.possibilities:
        return exc
    prog = ctx.command_path.split()[0]
    rest = " ".join(ctx.command_path.split()[1:])
    return click.NoSuchOption(
        exc.option_name,
        message=(
            f"No such option: {exc.option_name}. It is an option of "
            f"'{prog}', not of '{ctx.command_path}', so it has to come "
            f"before the command: {prog} {usage} {rest}"
        ),
        ctx=ctx,
    )


class _RootOptionHintCommand(TyperCommand):
    """A command whose unknown-option errors get the root-option hint."""

    def parse_args(self, ctx, args):
        try:
            return super().parse_args(ctx, args)
        except click.NoSuchOption as exc:
            raise _root_option_hint(ctx, exc) from None


class _RootOptionHintGroup(TyperGroup):
    """A group whose unknown-option errors get the root-option hint."""

    def parse_args(self, ctx, args):
        try:
            return super().parse_args(ctx, args)
        except click.NoSuchOption as exc:
            raise _root_option_hint(ctx, exc) from None


def _op_params(op: Operation) -> list[inspect.Parameter]:
    """The op's CLI-facing parameters (its signature, minus ``ctx``).

    Mirrors :func:`osw.service.registry.bind`'s annotation resolution, but
    only needs ``op.fn`` -- no ``Context`` -- so it is safe to call at
    app-build time.
    """
    try:
        hints = get_type_hints(op.fn, include_extras=True)
    except Exception:
        hints = {}
    sig = inspect.signature(op.fn)
    params = [
        p.replace(annotation=hints.get(p.name, p.annotation))
        for p in list(sig.parameters.values())[1:]  # drop ctx
    ]

    if op.name == "set_slot":
        # set_slot's `content: Union[str, dict, list]` is left unmarked in
        # the core (osw.service.ops.slots): typer has no support for
        # arbitrary Union types (verified empirically -- building a command
        # with this annotation raises AssertionError at app-build time). The
        # CLI instead takes `content` as a plain string and coerces it to
        # JSON at invocation time in `_run`, but only when the sibling
        # `slot` argument's content model is "json" (see SLOTS); a blanket
        # JSON parser would silently turn plain-text content like "123"
        # into an int.
        params = [
            p.replace(annotation=str) if p.name == "content" else p for p in params
        ]

    return params


def _run(op: Operation, typer_ctx: typer.Context, kwargs: dict[str, Any]) -> None:
    opts = typer_ctx.obj or {}

    if op.name == "set_slot":
        slot = kwargs.get("slot")
        content_model = SLOTS.get(slot, {}).get("content_model")
        content = kwargs.get("content")
        if content_model == "json" and isinstance(content, str):
            kwargs["content"] = json_value(content)

    try:
        verbose = bool(opts.get("verbose"))
        # Before anything that can fail, so every error still reports which
        # files were read. --instance is validated against the credential file
        # this names, so the banner belongs above that check too. The env-file
        # line is suppressed unless the command is verbose or fails.
        config.log_config_sources(verbose=verbose)

        instance = opts.get("instance")
        if instance:
            try:
                config.set_active_instance(instance)
            except ValueError as exc:
                raise errors.UnknownInstance(str(exc)) from exc

        settings = config.load(strict=False)
        policy = Policy(
            capture_stdout=bool(opts.get("as_json")),
            errors_as_dicts=False,
            allow_writes=not opts.get("read_only"),
            allow_interactive=True,
        )
        context = Context(settings, policy)
        bound = bind(op, context)
        result = bound(**kwargs)
    except OpError as exc:
        if not verbose:
            config.log_env_file_source()
        typer.echo(f"{exc.type}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)
    except Exception as exc:
        if opts.get("verbose"):
            raise
        # A failing command still reports every source, even non-verbosely.
        config.log_env_file_source()
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(1)

    typer.echo(render(result, as_json=bool(opts.get("as_json"))))


def _make_command(op: Operation):
    """Build the typer command callable for ``op``."""
    op_params = _op_params(op)
    ctx_param = inspect.Parameter(
        "typer_ctx",
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=typer.Context,
    )

    def command(**kwargs: Any) -> None:
        typer_ctx = kwargs.pop("typer_ctx")
        _run(op, typer_ctx, kwargs)

    command.__name__ = op.fn.__name__
    command.__doc__ = inspect.getdoc(op.fn)
    command.__signature__ = inspect.Signature(parameters=[ctx_param, *op_params])
    annotations = {p.name: p.annotation for p in op_params}
    annotations["typer_ctx"] = typer.Context
    command.__annotations__ = annotations
    return command


_groups: dict[str, typer.Typer] = {}

# One line per command group. Without these ``osw --help`` lists eight bare
# group names with nothing next to them; a group missing an entry still works.
_GROUP_HELP = {
    "entity": "Read, write, export and delete entities.",
    "file": "Wiki file pages: metadata, inline text, and local transfer.",
    "instances": "The OSL instances this process can connect to: list them, "
    "or check each one.",
    "ledger": "The local provenance ledger of pages written from here.",
    "schema": "Category JSON Schemas.",
    "search": "Find pages. OSW pages are titled by OSW-ID, so use 'ask' "
    "to search by name.",
    "slot": "Read and write individual page slots.",
}

for _op in iter_operations(surface="cli"):
    _command = _make_command(_op)
    if _op.group is None:
        app.command(name=_op.command, cls=_RootOptionHintCommand)(_command)
    else:
        _sub = _groups.get(_op.group)
        if _sub is None:
            _sub = typer.Typer(cls=_RootOptionHintGroup)
            _groups[_op.group] = _sub
            app.add_typer(_sub, name=_op.group, help=_GROUP_HELP.get(_op.group))
        _sub.command(name=_op.command, cls=_RootOptionHintCommand)(_command)


if __name__ == "__main__":
    app()
