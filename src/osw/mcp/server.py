"""Entry point for the osw-mcp stdio server.

Run via the ``osw-mcp`` console script or ``python -m osw.mcp``. Connection
credentials come from the environment / a ``.env`` file (see
:mod:`osw.service.config`).
"""

from __future__ import annotations

import atexit
import inspect
import sys
from typing import Any, Optional

# ty cannot resolve these: the mcp extra is uninstallable alongside the dev
# group (anyio conflict, issue #139), so it is absent from the env ty runs in.
# The rest of this module is type-checked; drop the ignores once #139 is fixed.
from mcp.server import MCPServer  # ty: ignore[unresolved-import]
from mcp.types import ToolAnnotations  # ty: ignore[unresolved-import]

import osw
import osw.service.ops
from osw.service import config
from osw.service.config import Settings
from osw.service.context import Context, Policy
from osw.service.registry import Operation, bind, iter_operations

INSTRUCTIONS = """\
This server is pinned to exactly one OpenSemanticLab (OSL) instance for its
whole process lifetime; there is no tool to switch instances. Run one server
process per instance (a separate registration, its own env file) if you need
more than one.

Entity and page titles are full MediaWiki page names, e.g. "Item:OSW1234...",
never a bare id or label.

Before creating or updating an entity, fetch its category's JSON Schema
(get_category_schema) so the written jsondata validates against it.

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


def _build_server() -> tuple[MCPServer, Context]:
    """Build the MCPServer and the Context its tools are bound to.

    Loads and validates settings first so a missing-credential misconfiguration
    fails fast (before any osw call that could trigger an interactive prompt).
    Also fails fast unless a domain was configured *explicitly*: this server is
    statically pinned to one OSL instance for its whole lifetime, and which one
    that is has to be readable from the configuration rather than inferred.
    Deliberately stricter than :func:`config.get_active_domain`, which the CLI
    uses: there the instance is visible on the command line at every
    invocation, and ``--instance`` can override it per command.
    """
    # Before get_settings(), so a misconfiguration that makes loading raise
    # still reports which files were read. stderr, so it lands in the MCP
    # client's server log without touching the JSON-RPC stream on stdout.
    config.log_config_sources()
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


def main() -> None:
    """Console-script entry point: build the server and serve over stdio."""
    try:
        mcp, ctx = _build_server()
    except Exception as exc:
        print(f"[osw-mcp] failed to start: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    atexit.register(ctx.close)
    try:
        mcp.run(transport="stdio")
    finally:
        ctx.close()


if __name__ == "__main__":
    main()
