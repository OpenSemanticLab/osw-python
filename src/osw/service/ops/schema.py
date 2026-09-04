"""Schema introspection: fetch a category's JSON Schema so the model can build
valid entities before writing them."""

from __future__ import annotations

from osw.service.context import Context
from osw.service.registry import operation
from osw.service.serialization import maybe_truncate
from osw.wtsite import WtSite


@operation(
    group="schema",
    cli_name="get",
    read_only_hint=True,
    idempotent_hint=True,
    max_result_size_chars=200_000,
)
def get_category_schema(ctx: Context, category: str) -> dict:
    """Return the JSON Schema of a category (its ``jsonschema`` slot).

    ``category`` is a full category page name, e.g. ``Category:Item``. The
    schema is read directly from the page slot, which - unlike fetching and
    generating models - does not modify any local files. Use the returned
    schema to construct a valid ``jsondata`` payload for
    ``create_or_update_entity``.
    """
    page = ctx.osw.site.get_page(WtSite.GetPageParam(titles=[category])).pages[0]
    if not page.exists:
        return {"category": category, "exists": False, "schema": None}
    schema = page.get_slot_content("jsonschema")
    content, truncated = maybe_truncate(schema, ctx.settings.max_chars)
    return {
        "category": category,
        "exists": True,
        "schema": content,
        "truncated": truncated,
    }
