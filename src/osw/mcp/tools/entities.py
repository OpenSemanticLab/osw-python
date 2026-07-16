"""Entity tools: read entity JSON, export JSON-LD, create/update, delete."""

from __future__ import annotations

import sys
from typing import Optional

import osw.model.entity as model_entity
from osw.core import OSW, AddOverwriteClassOptions, OverwriteOptions
from osw.wtsite import WtSite

from .. import config
from ..connection import get_ledger, run_guarded
from ..serialization import maybe_truncate, to_jsonable

_OVERWRITE = {
    "true": OverwriteOptions.true,
    "false": OverwriteOptions.false,
    "only empty": OverwriteOptions.only_empty,
    "replace remote": AddOverwriteClassOptions.replace_remote,
    "keep existing": AddOverwriteClassOptions.keep_existing,
}


def _parse_overwrite(value: str):
    key = str(value).lower().strip()
    if key not in _OVERWRITE:
        raise ValueError(
            f"Invalid overwrite '{value}'. Valid options: {list(_OVERWRITE)}"
        )
    return _OVERWRITE[key]


def _resolve_category_class(category: str):
    """Find the generated model class whose ``type`` default targets ``category``.

    Avoids guessing the datamodel-code-generator class name; matches on the
    ``type`` default (e.g. ``["Category:OSW..."]``) instead.
    """
    for obj in vars(model_entity).values():
        if not isinstance(obj, type) or not hasattr(obj, "__fields__"):
            continue
        field = obj.__fields__.get("type")
        default = getattr(field, "default", None) if field is not None else None
        if default and category in default:
            return obj
    return None


def register(mcp, *, include_writes: bool) -> None:
    """Register entity tools; mutating ones only when ``include_writes``."""
    settings = config.get_settings()

    @mcp.tool()
    def get_entity(title: str) -> dict:
        """Return an entity's stored JSON data (its ``jsondata`` slot).

        ``title`` is a full page name, e.g. ``Item:OSW123...``. Reading the slot
        directly does not modify any local files.
        """

        def _run(osw):
            page = osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
            if not page.exists:
                return {"title": title, "exists": False, "jsondata": None}
            content, truncated = maybe_truncate(
                page.get_slot_content("jsondata"), settings.max_chars
            )
            return {
                "title": title,
                "exists": True,
                "jsondata": content,
                "url": page.get_url(),
                "truncated": truncated,
            }

        return run_guarded(_run)

    @mcp.tool()
    def export_entity_jsonld(
        title: str, mode: str = "expand", build_rdf: bool = False
    ) -> dict:
        """Export an entity as JSON-LD (and optionally RDF/Turtle).

        ``mode`` is one of expand | flatten | compact | frame. Note: this loads
        the entity with schema auto-fetch, which regenerates the local generated
        model module as a side effect.
        """

        def _run(osw):
            result = osw.load_entity(
                OSW.LoadEntityParam(titles=[title], autofetch_schema=True)
            )
            entities = result.entities
            if not isinstance(entities, list):
                entities = [entities]
            if not entities:
                return {"error": f"Entity '{title}' not found.", "type": "NotFound"}
            export = osw.export_jsonld(
                OSW.ExportJsonLdParams(
                    entities=entities, mode=mode, build_rdf_graph=build_rdf
                )
            )
            out = {
                "jsonld": to_jsonable(export.documents[0]) if export.documents else None
            }
            if build_rdf and export.graph is not None:
                out["rdf_turtle"] = export.graph.serialize(format="turtle")
            return out

        return run_guarded(_run)

    if not include_writes:
        return

    @mcp.tool()
    def create_or_update_entity(
        category: str,
        jsondata: dict,
        namespace: Optional[str] = None,
        overwrite: str = "keep existing",
        comment: Optional[str] = None,
    ) -> dict:
        """Create or update an entity of ``category`` from a ``jsondata`` payload.

        ``category`` is a full category page name (e.g. ``Category:Item``); use
        ``get_category_schema`` to learn the valid fields first. ``overwrite``
        controls update behavior: one of true | false | only empty |
        replace remote | keep existing. Records the resulting page(s) in the
        provenance ledger so they can be deleted without extra confirmation.
        """
        ledger = get_ledger()

        def _run(osw):
            fetch = osw.fetch_schema(
                OSW.FetchSchemaParam(schema_title=category, mode="append")
            )
            if fetch.error_messages:
                return {
                    "error": "; ".join(fetch.error_messages),
                    "type": "SchemaError",
                }
            cls = _resolve_category_class(category)
            if cls is None:
                return {
                    "error": (
                        f"Could not resolve a model class for '{category}' after "
                        "fetching its schema. Check the category page name."
                    ),
                    "type": "ClassNotFound",
                }
            try:
                entity = cls(**jsondata)
            except Exception as exc:
                return {
                    "error": f"jsondata does not validate against {category}: {exc}",
                    "type": "ValidationError",
                }
            store = osw.store_entity(
                OSW.StoreEntityParam(
                    entities=[entity],
                    namespace=namespace,
                    overwrite=_parse_overwrite(overwrite),
                    edit_comment=comment,
                    bot_edit=True,
                )
            )
            titles = list(store.pages.keys())
            for page_title in titles:
                ledger.record(
                    page_title,
                    op="create_or_update",
                    tool="create_or_update_entity",
                    change_id=store.change_id,
                    slots=["jsondata"],
                )
            return {
                "titles": titles,
                "change_id": store.change_id,
                "urls": [f"https://{settings.domain}/wiki/{t}" for t in titles],
            }

        return run_guarded(_run)

    @mcp.tool()
    def delete_entity(
        title: str,
        confirm_external_delete: bool = False,
        comment: Optional[str] = None,
    ) -> dict:
        """Delete a page by full title, guarded by provenance.

        Pages this server created/modified (tracked in the ledger) are deleted
        without extra confirmation. Deleting any other page requires
        ``confirm_external_delete=true``.
        """
        ledger = get_ledger()

        def _run(osw):
            tracked = ledger.is_tracked(title)
            if not tracked and not confirm_external_delete:
                return {
                    "error": (
                        f"Refusing to delete '{title}': it was not created by this "
                        "MCP server. Re-run with confirm_external_delete=true to "
                        "override."
                    ),
                    "type": "ExternalDeleteBlocked",
                    "title": title,
                }
            page = osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
            if not page.exists:
                return {
                    "title": title,
                    "deleted": False,
                    "error": f"Page '{title}' does not exist.",
                    "type": "NotFound",
                }
            if not tracked:
                print(
                    f"[osw-mcp] WARNING: deleting externally-created page "
                    f"'{title}' (confirm_external_delete=True)",
                    file=sys.stderr,
                )
            page.delete(comment or "[osw-mcp] delete")
            ledger.mark_deleted(title)
            return {"title": title, "deleted": True}

        return run_guarded(_run)
