"""Entity tools: read entity JSON, export JSON-LD, create/update, delete."""

from __future__ import annotations

from osw.service.ops import entities as _ops  # noqa: F401  (registers the operations)
from osw.service.registry import bind, iter_operations

from .. import connection
from ..registration import tool_kwargs


def register(mcp, *, include_writes: bool) -> None:
    """Register entity tools; mutating ones only when ``include_writes``."""
    ctx = connection.legacy_context(include_writes=include_writes)
    for op in iter_operations(surface="mcp", include_writes=include_writes):
        if op.group != "entity":
            continue
        mcp.tool(**tool_kwargs(op, ctx.settings))(bind(op, ctx))
