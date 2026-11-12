"""JSON-safety and truncation helpers for tool return values.

Tool results are sent over the wire as JSON and shown to a model, so they must
be JSON-serializable and reasonably small. These helpers cap list lengths and
large text/JSON blobs, flagging when truncation occurred so the caller can
narrow the query.
"""

from __future__ import annotations

import json
from typing import Any, List, Tuple


def to_jsonable(obj: Any) -> Any:
    """Best-effort conversion of ``obj`` into a JSON-serializable structure.

    Falls back to ``str`` for anything json cannot encode (dates, Paths, etc.).
    """
    return json.loads(json.dumps(obj, default=str, ensure_ascii=False))


def cap_list(items: List[Any], limit: int) -> Tuple[List[Any], int, bool]:
    """Cap a list to ``limit`` entries.

    Returns ``(capped_items, total_count, truncated)``.
    """
    items = list(items)
    total = len(items)
    if limit is not None and total > limit:
        return items[:limit], total, True
    return items, total, False


def maybe_truncate(value: Any, max_chars: int) -> Tuple[Any, bool]:
    """Truncate ``value`` if its JSON/text form exceeds ``max_chars``.

    For strings, the string is truncated directly. For other structures, the
    value is returned unchanged when small enough, otherwise a truncated JSON
    string of it is returned. Returns ``(value_or_truncated, truncated)``.
    """
    if value is None:
        return None, False
    if isinstance(value, str):
        if len(value) > max_chars:
            return value[:max_chars], True
        return value, False
    encoded = json.dumps(value, default=str, ensure_ascii=False)
    if len(encoded) > max_chars:
        return encoded[:max_chars], True
    return to_jsonable(value), False
