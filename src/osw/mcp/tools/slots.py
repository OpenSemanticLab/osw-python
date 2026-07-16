"""Full multi-slot page access: list slots, read a slot, write a slot.

OSW pages are multi-slot MediaWiki pages. The valid slot keys and their content
models come from :data:`osw.wtsite.SLOTS` (main, jsondata, jsonschema, header,
footer, template, header_template, footer_template, data_template,
schema_template).
"""

from __future__ import annotations

from typing import Optional, Union

from osw.wtsite import SLOTS, WtSite

from .. import config
from ..connection import get_ledger, run_guarded
from ..serialization import maybe_truncate


def _invalid_slot(slot: str) -> dict:
    return {
        "error": f"Unknown slot '{slot}'. Valid slots: {list(SLOTS)}",
        "type": "InvalidSlot",
    }


def register(mcp, *, include_writes: bool) -> None:
    """Register slot tools; the writer only when ``include_writes``."""
    settings = config.get_settings()

    @mcp.tool()
    def list_page_slots(title: str) -> dict:
        """List the slots present on a page with their content models."""

        def _run(osw):
            page = osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
            if not page.exists:
                return {
                    "title": title,
                    "exists": False,
                    "slots": [],
                    "valid_slot_keys": list(SLOTS),
                }
            slots = []
            for key in page._slots:
                content = page.get_slot_content(key)
                slots.append({
                    "key": key,
                    "content_model": page.get_slot_content_model(key),
                    "empty": content in (None, "", {}, []),
                })
            return {
                "title": title,
                "exists": True,
                "slots": slots,
                "valid_slot_keys": list(SLOTS),
            }

        return run_guarded(_run)

    @mcp.tool()
    def get_slot(title: str, slot: str) -> dict:
        """Return the content of a single slot of a page.

        ``slot`` must be one of the valid slot keys (see ``list_page_slots``).
        """
        if slot not in SLOTS:
            return _invalid_slot(slot)

        def _run(osw):
            page = osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
            if not page.exists or slot not in page._slots:
                return {"title": title, "slot": slot, "exists": False, "content": None}
            content, truncated = maybe_truncate(
                page.get_slot_content(slot), settings.max_chars
            )
            return {
                "title": title,
                "slot": slot,
                "exists": True,
                "content_model": page.get_slot_content_model(slot),
                "content": content,
                "truncated": truncated,
            }

        return run_guarded(_run)

    if not include_writes:
        return

    @mcp.tool()
    def set_slot(
        title: str,
        slot: str,
        content: Union[str, dict, list],
        comment: Optional[str] = None,
        create_if_missing: bool = True,
    ) -> dict:
        """Write the content of a single slot and save the page.

        JSON slots (jsondata, jsonschema) require an object/array; wikitext slots
        require a string. Records the page in the provenance ledger.
        """
        if slot not in SLOTS:
            return _invalid_slot(slot)
        content_model = SLOTS[slot]["content_model"]
        if content_model == "json" and not isinstance(content, (dict, list)):
            return {
                "error": f"Slot '{slot}' is JSON; content must be an object or array.",
                "type": "InvalidContent",
            }
        if content_model == "wikitext" and not isinstance(content, str):
            return {
                "error": f"Slot '{slot}' is wikitext; content must be a string.",
                "type": "InvalidContent",
            }
        ledger = get_ledger()

        def _run(osw):
            page = osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
            if slot not in page._slots:
                if not create_if_missing:
                    return {
                        "error": (
                            f"Slot '{slot}' does not exist on '{title}' and "
                            "create_if_missing is false."
                        ),
                        "type": "SlotMissing",
                    }
                page.create_slot(slot, content_model)
            page.set_slot_content(slot, content)
            page.edit(comment=comment or f"[osw-mcp] set_slot {slot}", bot_edit=True)
            ledger.record(title, op="update", tool="set_slot", slots=[slot])
            return {
                "title": title,
                "slot": slot,
                "changed": True,
                "url": page.get_url(),
            }

        return run_guarded(_run)
