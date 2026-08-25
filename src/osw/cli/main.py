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
from typing import Any, get_type_hints

import typer

# Registers every operation in osw.service.registry.REGISTRY as a side effect.
import osw.service.ops  # noqa: F401
from osw.service import config
from osw.service.context import Context, Policy
from osw.service.errors import OpError
from osw.service.params import json_value
from osw.service.registry import Operation, bind, iter_operations
from osw.wtsite import SLOTS

from .render import render

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def _callback(
    ctx: typer.Context,
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
    .env file (see ``osw.service.config``); no instance selection option is
    exposed here yet.
    """
    ctx.obj = {"as_json": as_json, "read_only": read_only, "verbose": verbose}


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

    settings = config.load(strict=False)
    policy = Policy(
        capture_stdout=bool(opts.get("as_json")),
        errors_as_dicts=False,
        allow_writes=not opts.get("read_only"),
        allow_interactive=True,
    )
    context = Context(settings, policy)
    bound = bind(op, context)

    try:
        result = bound(**kwargs)
    except OpError as exc:
        typer.echo(f"{exc.type}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)
    except Exception as exc:
        if opts.get("verbose"):
            raise
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

for _op in iter_operations(surface="cli"):
    _command = _make_command(_op)
    if _op.group is None:
        app.command(name=_op.command)(_command)
    else:
        _sub = _groups.get(_op.group)
        if _sub is None:
            _sub = typer.Typer()
            _groups[_op.group] = _sub
            app.add_typer(_sub, name=_op.group)
        _sub.command(name=_op.command)(_command)


if __name__ == "__main__":
    app()
