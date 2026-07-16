"""Schema introspection: fetch a category's JSON Schema so the model can build
valid entities before writing them."""

from __future__ import annotations

from osw.wtsite import WtSite

from .. import config
from ..connection import run_guarded
from ..serialization import maybe_truncate


def register(mcp) -> None:
    """Register the read-only schema tool on ``mcp``."""
    settings = config.get_settings()

    @mcp.tool()
    def get_category_schema(category: str) -> dict:
        """Return the JSON Schema of a category (its ``jsonschema`` slot).

        ``category`` is a full category page name, e.g. ``Category:Item``. The
        schema is read directly from the page slot, which - unlike fetching and
        generating models - does not modify any local files. Use the returned
        schema to construct a valid ``jsondata`` payload for
        ``create_or_update_entity``.
        """

        def _run(osw):
            page = osw.site.get_page(WtSite.GetPageParam(titles=[category])).pages[0]
            if not page.exists:
                return {"category": category, "exists": False, "schema": None}
            schema = page.get_slot_content("jsonschema")
            content, truncated = maybe_truncate(schema, settings.max_chars)
            return {
                "category": category,
                "exists": True,
                "schema": content,
                "truncated": truncated,
            }

        return run_guarded(_run)
