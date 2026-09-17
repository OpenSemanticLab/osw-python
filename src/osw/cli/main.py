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
from osw.service.streams import force_utf8
from osw.service.version import version_line
from osw.wtsite import SLOTS

from .render import render

# help_option_names adds -h as an alias for --help. A child context created
# for a subcommand or a subgroup inherits it from its parent context when the
# child sets none of its own (click.Context.__init__), so this one setting
# covers the whole command tree, not just the root. --help comes first: click
# builds its "Try '... --help' for help." hint from help_option_names[0], and
# every existing usage error already names --help, so putting -h first would
# have changed all of them.
app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["--help", "-h"]},
)


def _force_utf8_output() -> None:
    """Encode stdout and stderr as UTF-8, whatever the locale asks for.

    The mechanism lives in :func:`osw.service.streams.force_utf8`, which the
    osw-mcp server uses as well. stderr is covered as well as stdout, because
    ``Context.guard`` sends captured stdout to stderr under ``--json``.

    Called from the app callback, so it covers every command. Click prints
    help and rejects an unknown root-level name before any callback runs, so
    those paths keep the locale encoding. They carry no wiki content: every
    help string in this package is ASCII (held by a test), and rich
    substitutes its box-drawing characters once the stream is not UTF-8. What
    stays exposed is the name the user typed, echoed back in a usage error --
    an unknown command name or an unknown root option name. A name typed
    after the command is fine, because click resolves the command, runs this
    callback, and only then parses the command's own arguments. --version /
    -V also prints before this callback runs (its own callback is eager, like
    --help), but it names no wiki content either, and forces UTF-8 on stdout
    itself (see ``_version_callback``) rather than relying on this function.
    """
    force_utf8(sys.stdout, sys.stderr)


def _version_callback(value: bool) -> None:
    """Eager callback for --version / -V: print the line and exit.

    click processes an eager option's callback before a command's own
    callback body runs, so this needs no configuration, no credential file
    and no network -- the same reason ``--help`` works with none of those.
    It also runs before ``_force_utf8_output``, so it forces stdout to UTF-8
    itself: the line names the package's install directory, which a redirected
    stdout on Windows would otherwise encode with the locale encoding, raising
    ``UnicodeEncodeError`` on a path outside it. ``osw-mcp -V`` does the same
    (``osw.mcp.server.main``).
    """
    if value:
        force_utf8(sys.stdout)
        typer.echo(version_line("osw"))
        raise typer.Exit()


@app.callback()
def _callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the version and exit.",
        is_eager=True,
        callback=_version_callback,
    ),
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
    "--version": "--version",
    "-V": "-V",
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
    "skill": "Install the Claude Code skills that ship with this package.",
    "slot": "Read and write individual page slots.",
    "task": "Create, find and update tasks, projects and persons.",
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
