"""Full multi-slot page access: list slots, read a slot, write a slot.

OSW pages are multi-slot MediaWiki pages. The valid slot keys and their content
models come from :data:`osw.wtsite.SLOTS` (main, jsondata, jsonschema, header,
footer, template, header_template, footer_template, data_template,
schema_template).
"""

from __future__ import annotations

from typing import Optional, Union

from osw.service import errors
from osw.service.context import Context
from osw.service.ledger import LedgerRecord
from osw.service.registry import operation
from osw.service.serialization import maybe_truncate
from osw.wtsite import SLOTS, WtSite


@operation(
    group="slot",
    cli_name="list",
    read_only_hint=True,
    idempotent_hint=True,
)
def list_page_slots(ctx: Context, title: str) -> dict:
    """List the slots present on a page with their content models."""
    page = ctx.osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
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


@operation(
    group="slot",
    cli_name="get",
    read_only_hint=True,
    idempotent_hint=True,
)
def get_slot(ctx: Context, title: str, slot: str) -> dict:
    """Return the content of a single slot of a page.

    ``slot`` must be one of the valid slot keys (see ``list_page_slots``).
    """
    if slot not in SLOTS:
        raise errors.InvalidSlot(f"Unknown slot '{slot}'. Valid slots: {list(SLOTS)}")

    page = ctx.osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
    if not page.exists or slot not in page._slots:
        return {"title": title, "slot": slot, "exists": False, "content": None}
    content, truncated = maybe_truncate(
        page.get_slot_content(slot), ctx.settings.max_chars
    )
    return {
        "title": title,
        "slot": slot,
        "exists": True,
        "content_model": page.get_slot_content_model(slot),
        "content": content,
        "truncated": truncated,
    }


@operation(
    group="slot",
    cli_name="set",
    writes=True,
    destructive_hint=False,
    idempotent_hint=True,
    records=lambda r: (
        [LedgerRecord(title=r["title"], op="update", slots=[r["slot"]])]
        if r.get("changed")
        else []
    ),
)
def set_slot(
    ctx: Context,
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
        raise errors.InvalidSlot(f"Unknown slot '{slot}'. Valid slots: {list(SLOTS)}")
    content_model = SLOTS[slot]["content_model"]
    if content_model == "json" and not isinstance(content, (dict, list)):
        raise errors.InvalidContent(
            f"Slot '{slot}' is JSON; content must be an object or array."
        )
    if content_model == "wikitext" and not isinstance(content, str):
        raise errors.InvalidContent(
            f"Slot '{slot}' is wikitext; content must be a string."
        )

    page = ctx.osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
    if slot not in page._slots:
        if not create_if_missing:
            raise errors.SlotMissing(
                f"Slot '{slot}' does not exist on '{title}' and "
                "create_if_missing is false."
            )
        page.create_slot(slot, content_model)
    page.set_slot_content(slot, content)
    page.edit(comment=comment or f"[osw-mcp] set_slot {slot}", bot_edit=True)
    return {
        "title": title,
        "slot": slot,
        "changed": True,
        "url": page.get_url(),
    }
