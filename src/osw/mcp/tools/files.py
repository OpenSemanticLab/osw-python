"""File tools: path-free read/write of wiki file content.

No parameter on this surface may name a filesystem path (enforced by
``Operation``'s validator at import time); path-taking equivalents (download
to disk, upload from disk) are CLI-only, in ``osw.cli.ops``.
"""

from __future__ import annotations

from osw.service.ops import files as _ops  # noqa: F401  (registers the operations)
from osw.service.registry import bind, iter_operations

from .. import connection


def register(mcp, *, include_writes: bool) -> None:
    """Register file tools; the writer only when ``include_writes``."""
    ctx = connection.legacy_context(include_writes=include_writes)
    for op in iter_operations(surface="mcp", include_writes=include_writes):
        if op.group != "file":
            continue
        mcp.tool()(bind(op, ctx))
