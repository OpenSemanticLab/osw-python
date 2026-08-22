"""MCP tool groups for the osw-mcp server."""

from __future__ import annotations

from . import entities, files, instances, schema, search, slots, status


def register_all(mcp, *, include_writes: bool) -> None:
    """Register every tool group on ``mcp``.

    Mutating tools (create/update/delete/upload/set_slot) are only registered
    when ``include_writes`` is true, so a read-only server never exposes them.
    Instance-selection tools are always registered: they change server-local
    state (which OSL instance subsequent calls talk to), not wiki content.
    """
    search.register(mcp)
    schema.register(mcp)
    entities.register(mcp, include_writes=include_writes)
    files.register(mcp, include_writes=include_writes)
    slots.register(mcp, include_writes=include_writes)
    status.register(mcp)
    instances.register(mcp)
