"""Clear stored relations of existing user items (``--prune``).

The store merges with the stored page, so an absent key keeps the stored value.
The keys are therefore overwritten with an empty list in a second edit of the
page's jsondata slot.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from osw.wtsite import WtPage


def clear_jsondata_keys(osw: Any, title: str, keys: Iterable[str]) -> bool:
    """Set each present, non-empty key in the page's jsondata slot to ``[]``.

    The page is read with a new WtPage, which downloads the current revision and
    bypasses the WtSite page cache. Other keys are written back unchanged.
    Returns True if the page was written, False if nothing changed.
    """
    page = WtPage(wtSite=osw.site, title=title)
    content = page.get_slot_content("jsondata")
    if isinstance(content, str):
        content = json.loads(content)
    if not isinstance(content, dict):
        return False
    changed = False
    for key in keys:
        if key in content and content[key] not in (None, [], "", {}):
            content[key] = []
            changed = True
    if not changed:
        return False
    page.set_slot_content("jsondata", content)
    page.edit(comment="user-sync: prune")
    return True
