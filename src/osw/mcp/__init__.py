"""osw-mcp: an MCP server exposing a live OpenSemanticLab instance.

The server wraps :class:`osw.express.OswExpress` and serves it over the Model
Context Protocol (stdio) so MCP clients such as Claude Code can search, read,
write and manage entities, page slots and files on a live OSL instance.

``main`` is imported lazily so ``import osw.mcp`` does not require the optional
``mcp`` / ``python-dotenv`` dependencies unless the server is actually started.
"""

from __future__ import annotations

__all__ = ["main"]


def __getattr__(name: str):
    if name == "main":
        from .server import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
