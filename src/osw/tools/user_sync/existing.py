"""Load existing OSW User items so the sync can update in place.

Matches are keyed on the ``username`` field, so accounts already stored under a
different uuid are updated rather than duplicated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from osw.wiki_tools import SearchParam

from .config import USER_CATEGORY

# Results per semantic search request.
PAGE_SIZE = 1000


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


def _query_user_titles(
    osw: Any, category: str, limit: Optional[int] = None
) -> List[str]:
    """Return the titles of all items of a category, paging through the results.

    The next offset is the one the wiki reports (``query-continue-offset``), not
    the offset plus the page size, because the wiki can cut a page shorter.
    """
    titles: List[str] = []
    offset = 0
    while True:
        query = SearchParam(
            query=f"[[HasType::{category}]]|offset={offset}",
            limit=PAGE_SIZE,
            return_meta=True,
        )
        result = osw.site.semantic_search(query)[0]
        titles.extend(result.titles)
        if limit is not None and len(titles) >= limit:
            return titles[:limit]
        if not result.truncated:
            return titles
        if result.next_offset is None or result.next_offset <= offset:
            raise RuntimeError(
                f"The wiki reported the next offset {result.next_offset} after "
                f"offset {offset} for '{category}'. Paging cannot continue."
            )
        offset = result.next_offset


def load_existing_users(
    osw: Any,
    category: str = USER_CATEGORY,
    limit: Optional[int] = None,
) -> ExistingUsers:
    """Query and load all existing User items, indexed by username.

    Args:
        osw: An authenticated OSW connection exposing ``site.semantic_search``
            and ``load_entity``.
        category: The User category page title.
        limit: Load at most this many items (for testing).

    Raises:
        RuntimeError: If the wiki reports a next offset that does not advance.
    """
    titles = _query_user_titles(osw, category, limit)
    if not titles:
        return ExistingUsers()
    entities = _as_entity_list(osw.load_entity(titles))
    by_username: Dict[str, Any] = {}
    for entity in entities:
        username = getattr(entity, "username", None)
        if username:
            by_username[username] = entity
    return ExistingUsers(by_username=by_username)


def adopt_existing_pages(
    osw: Any, existing: ExistingUsers, proposed_users: List[Any]
) -> List[str]:
    """Add items that exist at a proposed user's deterministic page title.

    A user without a match by ``username`` would be created at its deterministic
    page title. If that page already exists (for example, it has no username or
    is not typed as a User), it is loaded and indexed under the proposed
    username, so the sync reconciles against it instead of creating it again.

    Returns:
        The page titles that were adopted.
    """
    candidates = [p for p in proposed_users if existing.get(p.username) is None]
    if not candidates:
        return []
    titles = [p.full_page_title for p in candidates]
    missing = set(osw._get_missing_page_titles(titles, confirm_delay_s=0))
    present = [p for p in candidates if p.full_page_title not in missing]
    if not present:
        return []
    entities = _as_entity_list(osw.load_entity([p.full_page_title for p in present]))
    by_uuid = {str(getattr(e, "uuid", None)): e for e in entities if e is not None}
    adopted: List[str] = []
    for proposed in present:
        entity = by_uuid.get(str(proposed.uuid))
        if entity is not None:
            existing.by_username[proposed.username] = entity
            adopted.append(proposed.full_page_title)
    return adopted
