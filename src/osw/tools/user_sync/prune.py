"""Clear stored relations of existing user items (``--prune``).

The store merges with the stored page, so an absent key keeps the stored value.
The keys are therefore changed in a second edit of the page's jsondata slot.
A key of a list or set field is overwritten with an empty list. A key of a
single-valued field is deleted, because an empty list is not a valid value for
it. A key that is not a field of User is deleted as well.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from opensemantic.base.v1 import User
from pydantic.v1.fields import SHAPE_SINGLETON

from osw.wtsite import WtPage

_EMPTY = (None, [], "", {})


def is_multi_valued(key: str) -> bool:
    """True if the User field is a list or a set, False for any other key."""
    model_field = User.__fields__.get(key)
    return model_field is not None and model_field.shape != SHAPE_SINGLETON


def needs_clearing(key: str, value: Any) -> bool:
    """True if a present stored value of ``key`` must be cleared by pruning.

    A list or set field needs it only when it is not empty. Any other key needs
    it whenever it is present, also with an empty value such as ``[]``, which is
    not a valid value for a single-valued field.
    """
    if is_multi_valued(key):
        return value not in _EMPTY
    return True


def clear_jsondata_keys(osw: Any, title: str, keys: Iterable[str]) -> bool:
    """Clear each key in the page's jsondata slot that needs_clearing selects.

    A list or set field becomes ``[]``. Any other key is deleted. The page is
    read with a new WtPage, which downloads the current revision and bypasses the
    WtSite page cache. Other keys are written back unchanged.
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
        if key in content and needs_clearing(key, content[key]):
            if is_multi_valued(key):
                content[key] = []
            else:
                del content[key]
            changed = True
    if not changed:
        return False
    page.set_slot_content("jsondata", content)
    page.edit(comment="user-sync: prune")
    return True
