"""Search and query tools: semantic (SMW ask), full-text, instances, SPARQL."""

from __future__ import annotations

from osw.service.ops import search as _ops  # noqa: F401  (registers the operations)
from osw.service.registry import bind, iter_operations

from .. import connection


def register(mcp) -> None:
    """Register the search tools on ``mcp``."""
    ctx = connection.legacy_context()
    for op in iter_operations(surface="mcp"):
        if op.group != "search":
            continue
        mcp.tool()(bind(op, ctx))
