"""Entity operations: read entity JSON, export JSON-LD, create/update, delete."""

from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

import osw.model.entity as model_entity
from osw.core import OSW, AddOverwriteClassOptions, OverwriteOptions
from osw.service import config, errors
from osw.service.context import Context
from osw.service.ledger import LedgerRecord
from osw.service.params import json_value
from osw.service.registry import operation
from osw.service.serialization import maybe_truncate, to_jsonable
from osw.wtsite import WtSite

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


@operation(group="entity", cli_name="get", read_only_hint=True, idempotent_hint=True)
def get_entity(ctx: Context, title: str) -> dict:
    """Return an entity's stored JSON data (its ``jsondata`` slot).

    ``title`` is a full page name, e.g. ``Item:OSW123...``. Reading the slot
    directly does not modify any local files.
    """
    page = ctx.osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
    if not page.exists:
        return {"title": title, "exists": False, "jsondata": None}
    content, truncated = maybe_truncate(
        page.get_slot_content("jsondata"), ctx.settings.max_chars
    )
    return {
        "title": title,
        "exists": True,
        "jsondata": content,
        "url": page.get_url(),
        "truncated": truncated,
    }


@operation(group="entity", cli_name="export", read_only_hint=True, idempotent_hint=True)
def export_entity_jsonld(
    ctx: Context, title: str, mode: str = "expand", build_rdf: bool = False
) -> dict:
    """Export an entity as JSON-LD (and optionally RDF/Turtle).

    ``mode`` is one of expand | flatten | compact | frame. Note: this loads
    the entity with schema auto-fetch, which regenerates the local generated
    model module as a side effect.
    """
    result = ctx.osw.load_entity(
        OSW.LoadEntityParam(titles=[title], autofetch_schema=True)
    )
    entities = result.entities
    if not isinstance(entities, list):
        entities = [entities]
    if not entities:
        raise errors.NotFound(f"Entity '{title}' not found.")
    export = ctx.osw.export_jsonld(
        OSW.ExportJsonLdParams(entities=entities, mode=mode, build_rdf_graph=build_rdf)
    )
    out = {"jsonld": to_jsonable(export.documents[0]) if export.documents else None}
    if build_rdf and export.graph is not None:
        out["rdf_turtle"] = export.graph.serialize(format="turtle")
    return out


@operation(
    group="entity",
    cli_name="put",
    writes=True,
    destructive_hint=False,
    idempotent_hint=True,
    records=lambda r: [
        LedgerRecord(
            title=t, op="create_or_update", change_id=r["change_id"], slots=["jsondata"]
        )
        for t in r["titles"]
    ],
)
def create_or_update_entity(
    ctx: Context,
    category: str,
    jsondata: Annotated[dict, typer.Option(parser=json_value)],
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
    fetch = ctx.osw.fetch_schema(
        OSW.FetchSchemaParam(schema_title=category, mode="append")
    )
    if fetch.error_messages:
        raise errors.SchemaError("; ".join(fetch.error_messages))
    cls = _resolve_category_class(category)
    if cls is None:
        raise errors.ClassNotFound(
            f"Could not resolve a model class for '{category}' after "
            "fetching its schema. Check the category page name."
        )
    try:
        entity = cls(**jsondata)
    except Exception as exc:
        raise errors.ValidationError(
            f"jsondata does not validate against {category}: {exc}"
        )
    store = ctx.osw.store_entity(
        OSW.StoreEntityParam(
            entities=[entity],
            namespace=namespace,
            overwrite=_parse_overwrite(overwrite),
            edit_comment=comment,
            bot_edit=True,
        )
    )
    titles = list(store.pages.keys())
    domain = config.get_active_domain()
    return {
        "titles": titles,
        "change_id": store.change_id,
        "urls": [f"https://{domain}/wiki/{t}" for t in titles],
    }


@operation(
    group="entity",
    cli_name="delete",
    writes=True,
    destructive_hint=True,
    requires_user_interaction=True,
)
def delete_entity(
    ctx: Context,
    title: str,
    confirm_external_delete: bool = False,
    comment: Optional[str] = None,
) -> dict:
    """Delete a page by full title, guarded by provenance.

    Pages this server created/modified (tracked in the ledger) are deleted
    without extra confirmation. Deleting any other page requires
    ``confirm_external_delete=true``.
    """
    tracked = ctx.ledger.is_tracked(title)
    if not tracked and not confirm_external_delete:
        raise errors.ExternalDeleteBlocked(
            f"Refusing to delete '{title}': it was not created by this "
            "MCP server. Re-run with confirm_external_delete=true to "
            "override.",
            extra={"title": title},
        )
    page = ctx.osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
    if not page.exists:
        raise errors.NotFound(
            f"Page '{title}' does not exist.",
            extra={"title": title, "deleted": False},
        )
    if not tracked:
        print(
            f"[osw-mcp] WARNING: deleting externally-created page "
            f"'{title}' (confirm_external_delete=True)",
            file=sys.stderr,
        )
    page.delete(comment or "[osw-mcp] delete")
    ctx.ledger.mark_deleted(title)
    return {"title": title, "deleted": True}
