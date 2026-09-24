"""Load existing OSW User items so the sync can update in place.

Matches are keyed on the ``username`` field, so accounts already stored under a
different uuid are updated rather than duplicated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import USER_CATEGORY


@dataclass
class ExistingUsers:
    """Existing User items indexed by their MediaWiki username."""

    by_username: Dict[str, Any] = field(default_factory=dict)

    def get(self, username: str) -> Optional[Any]:
        return self.by_username.get(username)


def _as_entity_list(result: Any) -> List[Any]:
    """Normalize load_entity output (single, list, or LoadEntityResult)."""
    if result is None:
        return []
    entities = getattr(result, "entities", None)
    if entities is not None:
        return list(entities)
    if isinstance(result, list):
        return result
    return [result]


def load_existing_users(
    osw: Any,
    category: str = USER_CATEGORY,
    limit: Optional[int] = None,
) -> ExistingUsers:
    """Query and load all existing User items, indexed by username.

    Args:
        osw: An authenticated OSW connection exposing ``query_instances`` and
            ``load_entity``.
        category: The User category page title.
        limit: Load at most this many items (for testing).
    """
    titles = osw.query_instances(category=category)
    if limit is not None:
        titles = titles[:limit]
    if not titles:
        return ExistingUsers()
    entities = _as_entity_list(osw.load_entity(titles))
    by_username: Dict[str, Any] = {}
    for entity in entities:
        username = getattr(entity, "username", None)
        if username:
            by_username[username] = entity
    return ExistingUsers(by_username=by_username)
