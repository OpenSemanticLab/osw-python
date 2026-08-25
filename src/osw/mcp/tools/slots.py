"""Full multi-slot page access: list slots, read a slot, write a slot.

OSW pages are multi-slot MediaWiki pages. The valid slot keys and their content
models come from :data:`osw.wtsite.SLOTS` (main, jsondata, jsonschema, header,
footer, template, header_template, footer_template, data_template,
schema_template).
"""

from __future__ import annotations

from osw.service.ops import slots as _ops  # noqa: F401  (registers the operations)
from osw.service.registry import bind, iter_operations

from .. import connection


def register(mcp, *, include_writes: bool) -> None:
    """Register slot tools; the writer only when ``include_writes``."""
    ctx = connection.legacy_context(include_writes=include_writes)
    for op in iter_operations(surface="mcp", include_writes=include_writes):
        if op.group != "slot":
            continue
        mcp.tool()(bind(op, ctx))
