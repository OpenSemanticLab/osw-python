"""Status / whoami tool: report connection and configuration (no secrets)."""

from __future__ import annotations

from osw.service.ops import status as _ops  # noqa: F401  (registers the operations)
from osw.service.registry import bind, iter_operations

from .. import connection

_NAMES = ("status",)


def register(mcp) -> None:
    """Register the read-only status tool on ``mcp``."""
    ctx = connection.legacy_context()
    for op in iter_operations(surface="mcp"):
        if op.name not in _NAMES:
            continue
        mcp.tool()(bind(op, ctx))
