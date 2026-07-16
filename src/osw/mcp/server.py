"""Entry point for the osw-mcp stdio server.

Run via the ``osw-mcp`` console script or ``python -m osw.mcp``. Connection
credentials come from the environment / a ``.env`` file (see
:mod:`osw.mcp.config`).
"""

from __future__ import annotations

import atexit
import sys

from mcp.server.fastmcp import FastMCP

from . import config, connection
from .tools import register_all


def create_server() -> FastMCP:
    """Build the FastMCP server, registering tools per the read-only setting.

    Loads and validates settings first so a missing-credential misconfiguration
    fails fast (before any osw call that could trigger an interactive prompt).
    """
    settings = config.get_settings()
    mcp = FastMCP("osw")
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
        mcp.run()  # defaults to stdio transport
    finally:
        connection.shutdown()


if __name__ == "__main__":
    main()
