"""Entity operations: read entity JSON, export JSON-LD, create/update, delete."""

from __future__ import annotations

import copy
import logging
from typing import Annotated, Optional

import typer
from jsonschema.validators import validator_for

import osw.model.entity as model_entity
from osw.core import OSW, AddOverwriteClassOptions, OverwriteOptions
from osw.service import config, errors
from osw.service.context import Context
from osw.service.ledger import LedgerRecord
from osw.service.ops.schema import _resolve_schema
from osw.service.params import json_value
from osw.service.registry import operation
from osw.service.serialization import maybe_truncate, to_jsonable
from osw.wtsite import WtSite

_logger = logging.getLogger(__name__)

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


def _auto_filled_fields() -> set:
    """Field names the osw base model actually supplies a value for.

    ``create_or_update_entity`` validates by constructing the category's
    generated subclass, and every generated class inherits from ``Entity``.
    A field counts here only when the base model gives it a value on
    construction, through a default factory or a non-``None`` default -
    ``uuid`` (a fresh ``uuid4``) and ``type`` (the category default) are the
    two this matters for in practice. Most other fields are merely optional
    on ``Entity`` and default to ``None``, which is not a supplied value: a
    category subclass may still declare one of them required, in which case
    omitting it from the payload does make ``create_or_update_entity`` fail,
    so it must stay required here too. Reading the field set off the base
    class rather than naming the fields keeps this correct if the base model
    changes.
    """
    return {
        name
        for name, field in model_entity.Entity.__fields__.items()
        if field.required is False
        and (field.default_factory is not None or field.default is not None)
    }


def _strip_remote_refs(node, path: str, unchecked_refs: list) -> object:
    """Return a copy of ``node`` with every remote ``$ref`` replaced by ``{}``.

    A ``$ref`` is remote when its value does not start with ``#`` (a local
    JSON pointer); OSL schemas instead point ``$ref`` at a URL that reads
    another wiki page's schema, which a JSON Schema validator would try to
    fetch over the network. ``{}`` is the empty schema, which accepts
    anything, so that part of the payload is simply left unchecked. Each
    replacement's location is appended to ``unchecked_refs`` as a JSON path
    such as ``$.properties.parent``.
    """
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and not ref.startswith("#"):
            unchecked_refs.append(path)
            return {}
        return {
            key: _strip_remote_refs(value, f"{path}.{key}", unchecked_refs)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [
            _strip_remote_refs(item, f"{path}[{index}]", unchecked_refs)
            for index, item in enumerate(node)
        ]
    return node


@operation(
    group="entity", cli_name="validate", read_only_hint=True, idempotent_hint=True
)
def validate_entity(
    ctx: Context,
    category: str,
    jsondata: Annotated[dict, typer.Option(parser=json_value)],
) -> dict:
    """Check whether ``jsondata`` validates against ``category``'s resolved
    JSON Schema, without writing anything.

    Resolves ``category``'s effective JSON Schema across its parent chain -
    the same walk ``get_category_schema(resolve=True)`` performs - and
    validates ``jsondata`` against it with the ``jsonschema`` package.
    Passing here does not guarantee ``create_or_update_entity`` will
    succeed: that operation validates by constructing the generated
    pydantic model instead, a different check with different rules, and it
    also fetches the category's schema and regenerates the local
    ``osw.model.entity`` module as a side effect, which this operation never
    does.

    ``unknown_fields`` lists top-level keys of ``jsondata`` that are not
    declared in the resolved schema's ``properties``. This is the check
    that matters most in practice: most OSL schemas do not set
    ``additionalProperties: false``, so the validator itself would silently
    accept a plausible but wrong field name. ``unchecked_refs`` lists the
    JSON paths of parts of the schema that were not checked, because they
    were a remote ``$ref`` - a URL pointing at another wiki page rather than
    a local JSON pointer; validating against it would require a network
    call, so that part of the payload is left unchecked instead.

    Returns ``{category, valid, errors, unknown_fields, unchecked_refs,
    sources, skipped, auto_filled}``, where ``sources`` are the page titles
    successfully read while resolving the schema and ``skipped`` names every
    page the walk visited and could not use, and why - the walk's depth
    limit was reached, the page does not exist, it has no schema slot, it
    could not be read, or its slot did not parse. A non-empty ``skipped``
    means part of the category's inherited schema could not be read, so the
    check was made against less than the full schema and ``valid: true`` is
    weaker than it looks. ``auto_filled`` lists fields the category's schema
    marks required but the osw model supplies by itself, so they were not
    required here; ``uuid`` and ``type`` are the usual ones - omitting them
    from a payload is fine, since ``create_or_update_entity`` generates a
    uuid and sets the type from the category. An invalid payload is this
    operation's normal, successful answer: ``valid`` is False and ``errors``
    holds one message per validation error, each including its JSON path;
    this never raises for a bad payload. Raises ``errors.NotFound`` if
    ``category`` does not exist, and ``errors.SchemaError`` if the resolved
    schema could not actually be read (its ``jsonschema`` slot is missing,
    empty or unparsable, or ``category`` is not a category page at all) or
    is not itself a valid JSON Schema - in both cases the payload was not
    checked.
    """
    page = ctx.osw.site.get_page(WtSite.GetPageParam(titles=[category])).pages[0]
    if not page.exists:
        raise errors.NotFound(f"Category '{category}' does not exist.")

    merged_schema, sources, skipped = _resolve_schema(ctx, category)
    if not merged_schema or not merged_schema.get("properties"):
        raise errors.SchemaError(
            f"Could not read a JSON Schema for '{category}': its "
            "'jsonschema' slot is missing, empty or unparsable, or "
            "'category' is not a category page. The payload was not checked."
        )

    # Strip remote $refs on a deep copy, so this validation-only check never
    # mutates the schema _resolve_schema built.
    unchecked_refs: list = []
    schema = _strip_remote_refs(copy.deepcopy(merged_schema), "$", unchecked_refs)

    # Drop the required fields the model fills in itself, so a payload that
    # create_or_update_entity would accept is not reported invalid here. A
    # malformed 'required' (not a list, or holding an unhashable item) is
    # left alone here and surfaces as a SchemaError below, from check_schema,
    # rather than raising a raw TypeError from this step.
    required = schema.get("required")
    auto_filled = (
        sorted(
            {name for name in required if isinstance(name, str)} & _auto_filled_fields()
        )
        if isinstance(required, list)
        else []
    )
    if auto_filled:
        schema["required"] = [
            name for name in schema["required"] if name not in auto_filled
        ]

    try:
        validator_cls = validator_for(schema)
        validator_cls.check_schema(schema)
        validator = validator_cls(schema)
    except Exception as exc:
        raise errors.SchemaError(
            f"The resolved schema for '{category}' is not a valid JSON Schema: {exc}"
        )

    try:
        validation_errors = [
            f"{err.json_path}: {err.message}" for err in validator.iter_errors(jsondata)
        ]
    except Exception as exc:
        # An unresolvable local $ref (one iter_errors actually tries to
        # follow, unlike the remote ones stripped above) raises instead of
        # yielding, so surface it the same way a malformed schema is.
        raise errors.SchemaError(f"Could not validate '{category}': {exc}")
    declared = set(schema.get("properties") or {})
    unknown_fields = [key for key in jsondata if key not in declared]

    return {
        "category": category,
        "valid": not validation_errors,
        "errors": validation_errors,
        "unknown_fields": unknown_fields,
        "unchecked_refs": unchecked_refs,
        "sources": sources,
        "skipped": skipped,
        "auto_filled": auto_filled,
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
        _logger.warning(
            f"{config.log_prefix()} deleting externally-created page "
            f"'{title}' (confirm_external_delete=True)"
        )
    page.delete(comment or f"{config.log_prefix()} delete")
    ctx.ledger.mark_deleted(title)
    return {"title": title, "deleted": True}
