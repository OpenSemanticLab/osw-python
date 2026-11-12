"""Load existing OSW User items so the sync can update in place.

Matches are keyed on the ``username`` field, so accounts already stored under a
different uuid are updated rather than duplicated.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from osw.core import OSW
from osw.wiki_tools import SearchParam
from osw.wtsite import WtSite

from .config import USER_CATEGORY

# Results per semantic search request.
PAGE_SIZE = 1000


@dataclass
class ExistingUsers:
    """Existing User items indexed by their MediaWiki username."""

    by_username: Dict[str, Any] = field(default_factory=dict)
    # The jsondata as stored on the page, per username. The loaded entity cannot
    # tell a stored value from a model default.
    stored_jsondata: Dict[str, dict] = field(default_factory=dict)

    def get(self, username: str) -> Optional[Any]:
        return self.by_username.get(username)

    def get_stored(self, username: str) -> Optional[dict]:
        return self.stored_jsondata.get(username)


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


def _load_with_stored(osw: Any, titles: List[str]) -> Tuple[List[Any], Dict[str, dict]]:
    """Load the entities and read the stored jsondata of the same pages.

    The pages are fetched once and handed to load_entity as offline pages, so the
    jsondata is read without a second request. A copy is taken first, because
    load_entity removes empty keys from the slot content in place.

    Returns:
        The entities and the stored jsondata keyed by the uuid in it.
    """
    pages = osw.site.get_page(WtSite.GetPageParam(titles=titles)).pages
    offline_pages = {page.title: page for page in pages}
    stored: Dict[str, dict] = {}
    for page in pages:
        jsondata = page.get_slot_content("jsondata")
        if isinstance(jsondata, dict):
            stored[str(jsondata.get("uuid"))] = copy.deepcopy(jsondata)
    result = osw.load_entity(
        OSW.LoadEntityParam(titles=titles, offline_pages=offline_pages)
    )
    return _as_entity_list(result), stored


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
    entities, stored = _load_with_stored(osw, titles)
    existing = ExistingUsers()
    for entity in entities:
        username = getattr(entity, "username", None)
        if username:
            existing.by_username[username] = entity
            jsondata = stored.get(str(getattr(entity, "uuid", None)))
            if jsondata is not None:
                existing.stored_jsondata[username] = jsondata
    return existing


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
    entities, stored = _load_with_stored(osw, [p.full_page_title for p in present])
    by_uuid = {str(getattr(e, "uuid", None)): e for e in entities if e is not None}
    adopted: List[str] = []
    for proposed in present:
        entity = by_uuid.get(str(proposed.uuid))
        if entity is not None:
            existing.by_username[proposed.username] = entity
            jsondata = stored.get(str(proposed.uuid))
            if jsondata is not None:
                existing.stored_jsondata[proposed.username] = jsondata
            adopted.append(proposed.full_page_title)
    return adopted
