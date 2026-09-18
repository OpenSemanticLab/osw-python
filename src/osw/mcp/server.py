"""Entry point for the osw-mcp stdio server.

Run via the ``osw-mcp`` console script or ``python -m osw.mcp``. Connection
credentials come from the environment / a ``.env`` file (see
:mod:`osw.service.config`).
"""

from __future__ import annotations

import argparse
import atexit
import inspect
import io
import sys
from typing import Any, Optional, Sequence, TextIO

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

import osw
import osw.service.ops
from osw.service import config
from osw.service.config import Settings
from osw.service.context import Context, Policy
from osw.service.registry import Operation, bind, iter_operations
from osw.service.streams import force_utf8
from osw.service.version import version_line

INSTRUCTIONS = """\
This server is pinned to exactly one OpenSemanticLab (OSL) instance for its
whole process lifetime; there is no tool to switch instances. Run one server
process per instance (a separate registration, its own env file) if you need
more than one.

Entity and page titles are full MediaWiki page names, e.g. "Item:OSW1234...",
never a bare id or label.

Before creating or updating an entity, get its category's JSON Schema with
get_category_schema(resolve=True) - the unresolved schema alone is usually
missing inherited properties - then check the payload with validate_entity
before writing it.

This server has no filesystem access: file content moves inline as text, not
as a path. For anything path-based (uploading/downloading a local file, the
provenance ledger's path), use the `osw` CLI instead.
"""


def _annotations(op: Operation) -> Optional[ToolAnnotations]:
    """Build ``ToolAnnotations`` from ``op``'s four hints.

    Returns ``None`` when every hint is unset, so a hint-less operation gets
    no ``annotations`` at all rather than an all-``None`` object.

    Built by explicit keyword, never ``**dict``: passing an unrecognized
    keyword to ``ToolAnnotations`` (verified empirically against the
    installed mcp SDK) is silently dropped rather than raising, so a
    misspelled field name would otherwise fail with no error and leave the
    hint permanently ``None``.
    """
    hints = (
        op.read_only_hint,
        op.destructive_hint,
        op.idempotent_hint,
        op.open_world_hint,
    )
    if all(hint is None for hint in hints):
        return None
    return ToolAnnotations(
        read_only_hint=op.read_only_hint,
        destructive_hint=op.destructive_hint,
        idempotent_hint=op.idempotent_hint,
        open_world_hint=op.open_world_hint,
    )


def _meta(op: Operation, settings: Settings) -> dict[str, Any]:
    """Build the MCP ``_meta`` dict for ``op``.

    ``anthropic/maxResultSizeChars`` always has a value: ``op``'s own limit
    if it declares one, else the server-wide default. ``requiresUserInteraction``
    is only present (and only ever ``True``) for operations that declare it.
    ``op.extra_meta`` is merged last, so it can override either key.
    """
    meta: dict[str, Any] = {
        "anthropic/maxResultSizeChars": op.max_result_size_chars or settings.max_chars,
    }
    if op.requires_user_interaction:
        meta["anthropic/requiresUserInteraction"] = True
    meta.update(op.extra_meta)
    return meta


def tool_kwargs(op: Operation, settings: Settings) -> dict[str, Any]:
    """Keyword arguments for ``mcp.tool(...)`` for one operation."""
    return {
        "name": op.name,
        "description": inspect.getdoc(op.fn),
        "annotations": _annotations(op),
        "meta": _meta(op, settings),
    }


def _build_server(report: Optional[TextIO] = None) -> tuple[MCPServer, Context]:
    """Build the MCPServer and the Context its tools are bound to.

    Loads and validates settings first so a missing-credential misconfiguration
    fails fast (before any osw call that could trigger an interactive prompt).
    Also fails fast unless a domain was configured *explicitly*: this server is
    statically pinned to one OSL instance for its whole lifetime, and which one
    that is has to be readable from the configuration rather than inferred.
    Deliberately stricter than :func:`config.get_active_domain`, which the CLI
    uses: there the instance is resolved per invocation and reported at
    startup, and ``--instance`` can override it per command.

    ``report`` receives the configuration source lines instead of stderr, so
    the caller decides whether to show them. With no ``report`` they are
    discarded.
    """
    # Set before any shared-code logging runs, so every "[xxx] ..." message
    # and wiki edit comment from shared code names this adapter. main() sets
    # it again before calling this function -- not as its first statement:
    # force_utf8, argument parsing and the --version branch run before it
    # there -- since main() prints on a start failure and this function is
    # also callable on its own, e.g. from tests.
    config.set_log_prefix("osw-mcp")
    # Before get_settings(), so a misconfiguration that makes loading raise
    # still reports which files were read. Into `report` rather than stderr:
    # these lines repeat the client's own server entry, so main() shows them
    # only when asked or when the start fails.
    config.log_config_sources(stream=report if report is not None else io.StringIO())
    settings = config.get_settings()
    domain = settings.domain
    if domain is None:
        available = ", ".join(config.available_iris()) or "(none)"
        raise RuntimeError(
            "No OSL instance configured. Set OSW_DOMAIN in this server's env "
            "block, or in the .env file named by OSW_ENV_FILE. The server "
            "never picks an instance for you, not even when a credential file "
            "holds exactly one iri, because which instance a tool call reaches "
            f"must be readable from the configuration. Available: {available}."
        )
    ctx = Context(
        settings,
        Policy(
            capture_stdout=True,
            errors_as_dicts=True,
            allow_writes=not settings.read_only,
            allow_interactive=False,
        ),
    )
    mcp = MCPServer("osw", instructions=INSTRUCTIONS, version=osw.__version__)
    for op in iter_operations(surface="mcp", include_writes=not settings.read_only):
        mcp.tool(**tool_kwargs(op, settings))(bind(op, ctx))
    return mcp, ctx


def create_server() -> MCPServer:
    """Build the MCPServer, registering tools per the read-only setting."""
    mcp, _ctx = _build_server()
    return mcp


# Wrapped by hand, below 80 columns, with the URL on a line of its own.
# argparse's default formatter re-wraps a description with textwrap
# (break_on_hyphens=True), so at some terminal widths a line ends with
# ".../osw-" and the next starts with "python/blob/...", splitting the URL.
# RawDescriptionHelpFormatter (below) prints this text verbatim instead.
_DESCRIPTION = (
    "Runs an MCP server for one OpenSemanticLab instance over stdio. An MCP\n"
    "client starts it, not a person from a shell. Configuration comes from\n"
    "environment variables, a .env file, or a credential file; see\n"
    "https://github.com/OpenSemanticLab/osw-python/blob/main/docs/tools/mcp.md."
)


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``osw-mcp`` console script.

    Parsing happens before :func:`_build_server`, so ``-h``, ``-V`` and an
    unrecognized argument never need credentials.
    """
    parser = argparse.ArgumentParser(
        prog="osw-mcp",
        description=_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        # argparse accepts an unambiguous abbreviation by default (e.g.
        # "--vers"); osw's own CLI (click) does not, so this is turned off to
        # match: an argument that is not exactly one of the two below is
        # rejected.
        allow_abbrev=False,
    )
    parser.add_argument(
        "-V",
        "--version",
        action="store_true",
        help="show the version and exit",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Console-script entry point: build the server and serve over stdio.

    ``argv`` follows ``sys.argv[1:]``'s convention: ``None`` (the default)
    reads the real command line, and a caller that wants to pass its own,
    such as a test or ``python -m osw.mcp``, gives an explicit list instead.
    """
    # Before any write below, including the usage error argparse prints for
    # an unrecognized argument, which echoes it back. An MCP client starts
    # this server with stderr on a pipe, so Python encodes it with the locale
    # encoding, cp1252 on a German Windows system. The report holds the
    # credential file path and the env file path, so a directory named
    # "Muller" with an umlaut is enough to reach the client's log mangled.
    # Reconfiguring in place also covers osw's own log handler, which holds
    # this same stream object.
    #
    # stdout is deliberately left alone. The SDK's stdio_server re-wraps the
    # binary buffer as UTF-8 itself, and claims file descriptor 1 while doing
    # it, so the JSON-RPC channel does not depend on this and changing it here
    # would only add a way to interfere.
    force_utf8(sys.stderr)
    args = _build_parser().parse_args(argv)

    if args.version:
        # No server runs on this path, so the reason above for leaving
        # stdout alone does not apply.
        force_utf8(sys.stdout)
        print(version_line("osw-mcp"))
        return

    # See _build_server for why this is set here too.
    config.set_log_prefix("osw-mcp")
    report = io.StringIO()
    try:
        mcp, ctx = _build_server(report)
    except Exception as exc:
        # A failed start is when the configuration sources matter most, so
        # they are printed even with OSW_VERBOSE unset.
        sys.stderr.write(report.getvalue())
        # a fatal startup message stays a print, not a log record: setting
        # OSW_LOG_LEVEL=OFF must not make the server fail silently.
        print(f"[osw-mcp] failed to start: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc

    if config.get_settings().verbose:
        sys.stderr.write(report.getvalue())
        sys.stderr.flush()

    atexit.register(ctx.close)
    try:
        mcp.run(transport="stdio")
    finally:
        ctx.close()


if __name__ == "__main__":
    main()
