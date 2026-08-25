"""Entry point for the osw-mcp stdio server.

Run via the ``osw-mcp`` console script or ``python -m osw.mcp``. Connection
credentials come from the environment / a ``.env`` file (see
:mod:`osw.service.config`).
"""

from __future__ import annotations

import atexit
import sys

from mcp.server import MCPServer

import osw
from osw.service import config

from . import connection
from .tools import register_all

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


def create_server() -> MCPServer:
    """Build the MCPServer, registering tools per the read-only setting.

    Loads and validates settings first so a missing-credential misconfiguration
    fails fast (before any osw call that could trigger an interactive prompt).
    Also fails fast if no instance resolves: this server is statically pinned
    to one OSL instance for its whole lifetime, so registering tools that
    would all fail at call time would be actively misleading.
    """
    settings = config.get_settings()
    domain = config.get_active_domain()
    if domain is None:
        available = ", ".join(config.available_iris()) or "(none)"
        raise RuntimeError(
            "No OSL instance resolved. Set OSW_DOMAIN (or OSW_ENV_FILE to "
            "point at a .env file that sets it), or configure a credential "
            "file (OSW_CRED_FILEPATH) holding exactly one iri. "
            f"Available: {available}."
        )
    mcp = MCPServer("osw", instructions=INSTRUCTIONS, version=osw.__version__)
    register_all(mcp, include_writes=not settings.read_only)
    return mcp


def main() -> None:
    """Console-script entry point: build the server and serve over stdio."""
    try:
        mcp = create_server()
    except Exception as exc:
        print(f"[osw-mcp] failed to start: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    atexit.register(connection.shutdown)
    try:
        mcp.run(transport="stdio")
    finally:
        connection.shutdown()


if __name__ == "__main__":
    main()
