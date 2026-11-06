"""Create ``User:<username>`` redirect pages pointing at the user item.

An existing user page with real content is never overwritten; only missing
pages or pages that are already redirects are (re)written.
"""

from __future__ import annotations

from typing import Any, Optional

from osw.wtsite import WtPage


def redirect_wikitext(item_title: str) -> str:
    return f"#REDIRECT [[{item_title}]]"


def is_redirect(content: str) -> bool:
    return content.lstrip().upper().startswith("#REDIRECT")


def ensure_redirect(osw: Any, username: str, item_title: str) -> Optional[str]:
    """Create or refresh ``User:<username>`` -> item redirect.

    Returns the page title if written, or None if skipped (a real page already
    exists, or the redirect is already correct).
    """
    title = f"User:{username}"
    target = redirect_wikitext(item_title)
    page = WtPage(wtSite=osw.site, title=title)
    if getattr(page, "exists", False):
        content = page.get_slot_content("main") or ""
        if content.strip() and not is_redirect(content):
            return None  # do not clobber a real user page
        if content.strip() == target:
            return None  # already correct
    page.set_slot_content("main", target)
    page.edit(comment="user-sync: redirect to user item")
    return title
