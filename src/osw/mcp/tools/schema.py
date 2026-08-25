"""Schema introspection: fetch a category's JSON Schema so the model can build
valid entities before writing them."""

from __future__ import annotations

from osw.service.ops import schema as _ops  # noqa: F401  (registers the operations)
from osw.service.registry import bind, iter_operations

from .. import connection


def register(mcp) -> None:
    """Register the read-only schema tool on ``mcp``."""
    ctx = connection.legacy_context()
    for op in iter_operations(surface="mcp"):
        if op.group != "schema":
            continue
        mcp.tool()(bind(op, ctx))
