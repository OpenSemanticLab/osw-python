"""Mapping from :class:`~osw.service.registry.Operation` metadata onto the
keyword arguments the mcp SDK's ``mcp.tool(...)`` decorator expects.

Kept in its own module rather than in :mod:`osw.mcp.server`: ``server.py``
imports ``tools/``, so ``tools/*.py`` importing back from ``server.py`` would
be circular. Once ``tools/`` is folded into ``server.py``, this module folds
in too.
"""

from __future__ import annotations

import inspect
from typing import Any, Optional

from mcp.types import ToolAnnotations

from osw.service.config import Settings
from osw.service.registry import Operation


def _annotations(op: Operation) -> Optional[ToolAnnotations]:
    """Build ``ToolAnnotations`` from ``op``'s four hints.

    Returns ``None`` when every hint is unset, so a hint-less operation gets
    no ``annotations`` at all rather than an all-``None`` object.

    Built by explicit keyword, never ``**dict``: passing an unrecognized
    keyword to ``ToolAnnotations`` (verified empirically against the
    installed mcp SDK) is silently dropped rather than raising, so a
    misspelled field name would otherwise fail with no error and leave the
    hint permanently ``None``.
    """
    hints = (
        op.read_only_hint,
        op.destructive_hint,
        op.idempotent_hint,
        op.open_world_hint,
    )
    if all(hint is None for hint in hints):
        return None
    return ToolAnnotations(
        read_only_hint=op.read_only_hint,
        destructive_hint=op.destructive_hint,
        idempotent_hint=op.idempotent_hint,
        open_world_hint=op.open_world_hint,
    )


def _meta(op: Operation, settings: Settings) -> dict[str, Any]:
    """Build the MCP ``_meta`` dict for ``op``.

    ``anthropic/maxResultSizeChars`` always has a value: ``op``'s own limit
    if it declares one, else the server-wide default. ``requiresUserInteraction``
    is only present (and only ever ``True``) for operations that declare it.
    ``op.extra_meta`` is merged last, so it can override either key.
    """
    meta: dict[str, Any] = {
        "anthropic/maxResultSizeChars": op.max_result_size_chars or settings.max_chars,
    }
    if op.requires_user_interaction:
        meta["anthropic/requiresUserInteraction"] = True
    meta.update(op.extra_meta)
    return meta


def tool_kwargs(op: Operation, settings: Settings) -> dict[str, Any]:
    """Keyword arguments for ``mcp.tool(...)`` for one operation."""
    return {
        "name": op.name,
        "description": inspect.getdoc(op.fn),
        "annotations": _annotations(op),
        "meta": _meta(op, settings),
    }
