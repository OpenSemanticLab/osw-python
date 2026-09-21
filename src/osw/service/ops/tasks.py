"""Task management operations: create/update/list tasks, projects, persons.

Narrow, field-based operations for OSL task management, built on three OSL
core categories (Task, Person, Project). Every operation takes plain typed
parameters and returns a small flat dict, so an agent driving this spends few
tokens; no JSON Schema is ever handed to the caller.
"""

from __future__ import annotations

import re
import warnings
from datetime import datetime
from typing import Optional
from uuid import uuid4

from osw.core import OSW, OverwriteOptions
from osw.service import config, errors
from osw.service.context import Context
from osw.service.ledger import LedgerRecord
from osw.service.ops.entities import _resolve_category_class
from osw.service.registry import operation
from osw.wtsite import WtSite

CATEGORY_TASK = "Category:OSWc5d4829ed2744a219ba027171c75fa1d"
CATEGORY_PERSON = "Category:OSW44deaa5b806d41a2a88594f562b110e9"
CATEGORY_PROJECT = "Category:OSWb2d7e6a2eff94c82b7f1f2699d5b0ee3"

# Fixed vocabularies. Both were verified on arkeve: each category holds
# exactly these three items and no others. The ids are the items' uuids and
# come from the shared OSL core data model, so they are the same on every
# instance that imports it; spot-checked on two further instances. An
# instance that defines its own items is still reachable, because
# _resolve_vocab passes a value already starting with "Item:" through.
STATUS_ITEMS = {
    "to do": "Item:OSWaa8d29404288446a9f3ec7afa4e2a512",
    "in work": "Item:OSWa2b4567ad4874ea1b9adfed19a3d06d1",
    "done": "Item:OSWf474ec34b7df451ea8356134241aef8a",
}
PRIO_ITEMS = {
    "high": "Item:OSW8743c7d03c4e46c1bd42bb05e1a082d9",
    "medium": "Item:OSW8d781c35212548fa9b2fccad3765da65",
    "low": "Item:OSWcaf7db070ad6407babc5245e84d76840",
}
# A few aliases so an agent mapping free text does not fail on wording. No
# aliases for priority; high, medium and low are unambiguous.
STATUS_ALIASES = {
    "todo": "to do",
    "open": "to do",
    "pending": "to do",
    "backlog": "to do",
    "in progress": "in work",
    "doing": "in work",
    "wip": "in work",
    "closed": "done",
    "complete": "done",
    "completed": "done",
    "finished": "done",
}

# These are fallbacks used only when the category @context cannot be read;
# the property names are normally derived from the wiki with
# WtSite.get_smw_property_map, so an instance that remaps a property is
# followed automatically.
PROP_STATUS = "HasStatus"
PROP_PRIO = "HasPriority"
PROP_RELATED_TO = "IsRelatedTo"
PROP_ACTIONEE = "HasActionee"
PROP_LABEL = "HasLabel"

# Maps a JSON field name to its fallback SMW property constant.
_PROP_FALLBACK = {
    "status": PROP_STATUS,
    "prio": PROP_PRIO,
    "related_to": PROP_RELATED_TO,
    "actionees": PROP_ACTIONEE,
    "label": PROP_LABEL,
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _write_category(kind: str) -> str:
    """Return the category a newly created 'task', 'person' or 'project' gets.

    A configured override wins; otherwise the core constant. Reading always
    uses the core constant instead, since MediaWiki category membership
    includes the whole subclass tree.
    """
    settings = config.get_settings()
    overrides = {
        "task": settings.task_category,
        "person": settings.person_category,
        "project": settings.project_category,
    }
    defaults = {
        "task": CATEGORY_TASK,
        "person": CATEGORY_PERSON,
        "project": CATEGORY_PROJECT,
    }
    return overrides[kind] or defaults[kind]


def _ensure_models(ctx: Context) -> None:
    """Make sure the generated Task/Person/Project model classes exist.

    Fetches the schemas only when a class is missing, guarded on
    ``_resolve_category_class(...) is not None`` rather than on a guessed
    class name, since ``fetch_schema`` rewrites the installed
    ``osw.model.entity`` module and reloads it, which is why this must run
    at most once per process.
    """
    wanted = [
        CATEGORY_TASK,
        _write_category("task"),
        CATEGORY_PERSON,
        _write_category("person"),
        CATEGORY_PROJECT,
        _write_category("project"),
    ]
    missing = [c for c in dict.fromkeys(wanted) if _resolve_category_class(c) is None]
    if not missing:
        return
    # fetch_schema turns the site page cache on and does not always turn it
    # back off. A cache left on makes a later read return a page revision
    # from before a write in the same process, so restore the state here.
    cache_state = ctx.osw.site.get_cache_enabled()
    try:
        fetch = ctx.osw.fetch_schema(
            OSW.FetchSchemaParam(schema_title=missing, mode="append")
        )
    finally:
        if cache_state:
            ctx.osw.site.enable_cache()
        else:
            ctx.osw.site.disable_cache()
    if fetch.error_messages:
        raise errors.SchemaError("; ".join(fetch.error_messages))


def _get_page_uncached(ctx: Context, title: str):
    """Download a page, bypassing the site page cache.

    An update must read the revision that is on the server right now. A
    cached page object can hold a revision from before a write made earlier
    in the same process, which would make the update write old field values
    back.
    """
    cache_state = ctx.osw.site.get_cache_enabled()
    ctx.osw.site.disable_cache()
    try:
        return ctx.osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
    finally:
        if cache_state:
            ctx.osw.site.enable_cache()


def _fallback_props(category: str, fields: list[str]) -> dict:
    """Return the fallback SMW property names for ``fields``.

    Raises ``errors.OpError`` instead of silently guessing when a field has
    no entry in ``_PROP_FALLBACK``, since a field name is not a valid
    property name and would build a query that returns nothing and reports
    no error.
    """
    missing = [f for f in fields if f not in _PROP_FALLBACK]
    if missing:
        raise errors.OpError(
            f"No built-in fallback Semantic MediaWiki property name for "
            f"field(s) {', '.join(missing)} of '{category}'; this operation "
            "cannot continue without reading the wiki's @context."
        )
    return {f: _PROP_FALLBACK[f] for f in fields}


def _smw_props(ctx: Context, category: str, fields: list[str]) -> dict:
    """Resolve the SMW property name of each field for a category.

    Reads the names from the category's ``@context``, via
    ``WtSite.get_smw_property_map``. That chain is resolved and cached in
    ``WtSite``, so it costs one read per category per process, not per call.
    If the schema pages cannot be read but the query API can, the fallback in
    ``_PROP_FALLBACK`` keeps a read working.
    """
    try:
        mapping = ctx.osw.site.get_smw_property_map(category)
    except Exception as exc:
        warnings.warn(
            f"Could not read the SMW property map for '{category}': {exc}. "
            "Using the built-in property names instead; a query will return "
            "nothing if the wiki remapped them."
        )
        return _fallback_props(category, fields)
    if not mapping:
        warnings.warn(
            f"The @context of '{category}' resolved to no Semantic MediaWiki "
            "properties; the category page is probably missing or "
            "unreadable. Using the built-in property names instead; a query "
            "will return nothing if the wiki remapped them."
        )
        return _fallback_props(category, fields)
    result = {}
    for field in fields:
        if field not in mapping:
            raise errors.OpError(
                f"The @context of '{category}' declares no Semantic MediaWiki "
                f"property for field '{field}', so this operation cannot query "
                "it. The field may have been renamed in the wiki's data model."
            )
        result[field] = mapping[field]
    return result


def _ask_rows(
    ctx: Context, query: str, printouts: list[str], limit: Optional[int] = None
) -> tuple[list[dict], bool]:
    """Run an SMW ask query that returns property values, not only titles."""
    lim = ctx.limit(limit)
    # The '=name' alias forces the printout key in the result to the property
    # name; without it, SMW keys the result by the property's display label,
    # which need not equal the property name, and the read-back below looks
    # the value up by name.
    full = query + "".join(f"|?{p}={p}" for p in printouts)
    raw = ctx.osw.site.semantic_search(
        WtSite.SearchParam(query=full, limit=lim, return_json=True)
    )
    response = raw[0] if raw else {}
    payload = response.get("query", {}).get("results", {})
    if not isinstance(payload, dict):
        # SMW serialises an empty result set as a JSON array, not an object.
        payload = {}
    rows = [p for p in payload.values() if p.get("exists") == "1"]
    # SMW marks a cut result set with a top-level continuation offset. A
    # complete set of exactly 'limit' rows carries no such key, so comparing
    # the row count against the limit would report a truncation that did not
    # happen. Measured on arkeve: limit=2 of 408 tasks gives the key, limit=500
    # does not.
    return rows, "query-continue-offset" in response


def _label_of(row: dict) -> str:
    """The display label of an ask result row.

    Does not request a ``|?Display_title_of`` printout: its printout key
    comes back translated into the wiki's content language. The top-level
    ``displaytitle`` is always present and is not translated away.
    """
    return row.get("displaytitle") or row["fulltext"]


def _resolve_vocab(value: str, table: dict, aliases: dict, field: str) -> str:
    """Map a human word to an ``Item:OSW...`` page name.

    A value already starting with ``Item:`` passes through unchanged, which
    lets a caller name a value an instance added itself.
    """
    if value.startswith("Item:"):
        return value
    key = value.lower().strip()
    key = aliases.get(key, key)
    if key not in table:
        accepted = ", ".join(sorted(table))
        raise errors.ValidationError(
            f"Invalid {field} '{value}'. Accepted values: {accepted}."
        )
    return table[key]


def _check_injection(value: str, field: str) -> None:
    """Reject a value that could change an ask query's structure."""
    if "]]" in value or "[[" in value or "|" in value:
        raise errors.ValidationError(f"{field} must not contain ']]', '[[' or '|'.")


def _resolve_ref(ctx: Context, value: str, category: str, kind: str) -> str:
    """Turn a project or person name (or an existing page name) into a page name."""
    if value.startswith("Item:"):
        return value
    _check_injection(value, kind)
    prop_label = _smw_props(ctx, category, ["label"])["label"]
    rows, _ = _ask_rows(
        ctx, f"[[{category}]][[{prop_label}::~*{value}*]]", [], limit=10
    )
    if len(rows) == 1:
        return rows[0]["fulltext"]
    if not rows:
        raise errors.NotFound(
            f"No {kind} matches '{value}'. Search with the CLI command "
            f"'osw search label \"{value}\" --category {category}' or the MCP "
            "tool 'search_by_label' to see candidates."
        )
    candidates = "; ".join(f"{_label_of(r)} ({r['fulltext']})" for r in rows)
    raise errors.ValidationError(
        f"Multiple {kind}s match '{value}': {candidates}. Pass the page name "
        "to choose one."
    )


def _resolve_due(value: str) -> str:
    """Normalize a due date/time to the ``end_date_time`` field's ISO 8601 form.

    Accepts ``YYYY-MM-DD`` (turned into midnight UTC) or a full ISO 8601
    timestamp; anything else is rejected.
    """
    text = value.strip()
    date_only = bool(_DATE_RE.match(text))
    # The regex only checks the shape, so parse as well; without this an
    # impossible date such as 2026-13-45 would pass straight through.
    candidate = f"{text}T00:00:00" if date_only else text.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(candidate)
    except ValueError:
        raise errors.ValidationError(
            f"Invalid due date/time '{value}'. Use 'YYYY-MM-DD' or full ISO 8601."
        )
    return f"{text}T00:00:00Z" if date_only else text


def _resolved_refs(jsondata: dict) -> dict:
    """Copy the page-reference lists out of ``jsondata`` before it is stored.

    Building the model empties ``related_to`` and ``actionees`` in the dict
    it is given. ``cls(**jsondata)`` passes the list objects by reference, and
    ``oold.model.v1.LinkedBaseModel.__init__`` moves each page name into
    ``__iris__`` by calling ``list.remove`` on that shared object. The entity
    and the page it writes are both correct; only a caller reading its own
    dict afterwards sees an empty list. Measured with oold 0.16.2.
    """
    return {
        "related_to": list(jsondata.get("related_to") or []),
        "actionees": list(jsondata.get("actionees") or []),
    }


def _store(ctx: Context, category: str, jsondata: dict, comment: str) -> dict:
    """Build the entity against ``category``'s model and store it.

    ``overwrite=true`` is correct here because both callers (``create_task``
    and ``update_task``) send the complete record, so there is nothing to
    preserve on the server.
    """
    _ensure_models(ctx)
    cls = _resolve_category_class(category)
    if cls is None:
        raise errors.ClassNotFound(
            f"Could not resolve a model class for '{category}' after "
            "fetching its schema."
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
            overwrite=OverwriteOptions.true,
            edit_comment=comment,
            bot_edit=True,
        )
    )
    titles = list(store.pages.keys())
    # store_entity reports a page title even when the upload was skipped, so
    # confirm the pages are really there. Without this an operation can
    # return a title and a change_id for a page that was never written.
    absent = [t for t in titles if not _get_page_uncached(ctx, t).exists]
    if absent:
        raise errors.OpError(
            f"Storing {category} reported success but these pages do not "
            f"exist: {', '.join(absent)}. Do not repeat the write before "
            f"opening one of them; on a replicated wiki the read can be "
            f"served by a replica that has not caught up yet."
        )
    domain = config.get_active_domain()
    return {
        "titles": titles,
        "change_id": store.change_id,
        "urls": [f"https://{domain}/wiki/{t}" for t in titles],
    }


@operation(
    group="task",
    cli_name="create",
    writes=True,
    destructive_hint=False,
    idempotent_hint=False,
    records=lambda r: [
        LedgerRecord(
            title=t, op="create_task", change_id=r["change_id"], slots=["jsondata"]
        )
        for t in r["titles"]
    ],
)
def create_task(
    ctx: Context,
    label: str,
    description: Optional[str] = None,
    status: Optional[str] = None,
    prio: Optional[str] = None,
    project: Optional[str] = None,
    actionees: Optional[list[str]] = None,
    due: Optional[str] = None,
    lang: str = "en",
) -> dict:
    """Create a new task.

    ``status`` accepts a human word (to do, in work, done, or an alias like
    'in progress') and defaults to "to do" when omitted. ``prio`` accepts
    high, medium or low and is left unset when omitted. ``project`` and each
    of ``actionees`` accept either an existing page name (``Item:OSW...``)
    or a label to look up; an absent or ambiguous match raises rather than
    guessing. When ``actionees`` is omitted entirely, no actionee is
    assigned; the operator is never assigned silently. ``due`` maps to the
    task's end time, since the Task category has no due-date property;
    accepts ``YYYY-MM-DD`` (midnight UTC) or a full ISO 8601 timestamp.

    Use ``search_ask`` filtered by ``project`` first as a duplicate check: an
    exact label match within the same project means the task already exists.

    Returns ``{title, url, uuid, change_id, titles, urls, related_to,
    actionees}`` for the created page. ``related_to`` and ``actionees`` are
    the page names the given labels resolved to, so the caller can confirm
    which entity was chosen; a label search matches a substring, so a single
    match is accepted without any further confirmation.
    """
    task_uuid = str(uuid4())
    jsondata: dict = {
        "type": [_write_category("task")],
        "uuid": task_uuid,
        "label": [{"text": label, "lang": lang}],
    }
    if description is not None:
        jsondata["description"] = [{"text": description, "lang": lang}]
    jsondata["status"] = _resolve_vocab(
        status or "to do", STATUS_ITEMS, STATUS_ALIASES, "status"
    )
    if prio is not None:
        jsondata["prio"] = _resolve_vocab(prio, PRIO_ITEMS, {}, "prio")
    if project is not None:
        jsondata["related_to"] = [
            _resolve_ref(ctx, project, CATEGORY_PROJECT, "project")
        ]
    if actionees is not None:
        jsondata["actionees"] = [
            _resolve_ref(ctx, a, CATEGORY_PERSON, "person") for a in actionees
        ]
    if due is not None:
        jsondata["end_date_time"] = _resolve_due(due)

    # Copy the resolved references before storing. The page is written
    # correctly, but building the model empties these lists inside the dict
    # passed to it, so reading them afterwards would report nothing.
    resolved = _resolved_refs(jsondata)
    result = _store(
        ctx, _write_category("task"), jsondata, "Created by osw task create"
    )
    return {
        "title": result["titles"][0],
        "url": result["urls"][0],
        "uuid": task_uuid,
        "change_id": result["change_id"],
        "titles": result["titles"],
        "urls": result["urls"],
        **resolved,
    }


@operation(
    group="task",
    cli_name="update",
    writes=True,
    destructive_hint=False,
    idempotent_hint=True,
    records=lambda r: [
        LedgerRecord(
            title=r["title"],
            op="update_task",
            change_id=r["change_id"],
            slots=["jsondata"],
        )
    ],
)
def update_task(
    ctx: Context,
    title: str,
    label: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    prio: Optional[str] = None,
    project: Optional[str] = None,
    actionees: Optional[list[str]] = None,
    due: Optional[str] = None,
    lang: str = "en",
) -> dict:
    """Update a task by merging the given fields into its stored record.

    Only the parameters actually passed are changed; a parameter left as
    ``None`` leaves the stored field untouched. Resolution rules for
    ``status``, ``prio``, ``project``, ``actionees`` and ``due`` are the
    same as ``create_task``. Setting a field to an empty value is out of
    scope here; to clear a field, edit the entity with ``osw entity put``.

    ``project`` and ``actionees`` replace the stored list, they do not add to
    it. Passing one actionee removes every other actionee the task had, and
    passing one project removes every other related project. To add someone,
    read the current actionees with ``get_entity`` and pass the full list.

    Returns ``{title, url, change_id, changed, related_to, actionees}``, where
    ``changed`` is the sorted list of field names that were actually written,
    and ``related_to``/``actionees`` are the stored page names after the
    update, so the caller can confirm which entity each name resolved to.
    """
    page = _get_page_uncached(ctx, title)
    if not page.exists:
        raise errors.NotFound(f"Task '{title}' does not exist.")
    stored = page.get_slot_content("jsondata")
    jsondata = dict(stored)
    changed = []

    if label is not None:
        jsondata["label"] = [{"text": label, "lang": lang}]
        changed.append("label")
    if description is not None:
        jsondata["description"] = [{"text": description, "lang": lang}]
        changed.append("description")
    if status is not None:
        jsondata["status"] = _resolve_vocab(
            status, STATUS_ITEMS, STATUS_ALIASES, "status"
        )
        changed.append("status")
    if prio is not None:
        jsondata["prio"] = _resolve_vocab(prio, PRIO_ITEMS, {}, "prio")
        changed.append("prio")
    if project is not None:
        jsondata["related_to"] = [
            _resolve_ref(ctx, project, CATEGORY_PROJECT, "project")
        ]
        changed.append("related_to")
    if actionees is not None:
        jsondata["actionees"] = [
            _resolve_ref(ctx, a, CATEGORY_PERSON, "person") for a in actionees
        ]
        changed.append("actionees")
    if due is not None:
        jsondata["end_date_time"] = _resolve_due(due)
        changed.append("end_date_time")

    # Keep the existing uuid untouched; keep the existing type unless the
    # stored record has none.
    if not jsondata.get("type"):
        jsondata["type"] = [_write_category("task")]
    category = jsondata["type"][0]

    resolved = _resolved_refs(jsondata)
    result = _store(ctx, category, jsondata, "Updated by osw task update")
    return {
        "title": result["titles"][0],
        "url": result["urls"][0],
        "change_id": result["change_id"],
        "changed": sorted(changed),
        **resolved,
    }


@operation(
    group="task",
    cli_name="create-person",
    writes=True,
    destructive_hint=False,
    idempotent_hint=False,
    records=lambda r: [
        LedgerRecord(
            title=t, op="create_person", change_id=r["change_id"], slots=["jsondata"]
        )
        for t in r["titles"]
    ],
)
def create_person(
    ctx: Context, first_name: str, surname: str, email: Optional[str] = None
) -> dict:
    """Create a new person entity.

    This is a fallback, not the normal path: most OSL instances create
    persons through their own process or workflow, and an instance usually
    already holds every person you need. Search with ``search_by_label`` first,
    and only create one when the person is genuinely absent.

    The label is built here as "<first_name> <surname>". The Person schema
    derives it from the two name fields through a form-editor template, but
    that template only runs in the browser form, so a record written through
    the API has to carry its own label.

    Returns ``{title, url, uuid, change_id, titles, urls}``.
    """
    person_uuid = str(uuid4())
    jsondata: dict = {
        "type": [_write_category("person")],
        "uuid": person_uuid,
        "first_name": first_name,
        "surname": surname,
        "label": [{"text": f"{first_name} {surname}", "lang": "en"}],
    }
    if email is not None:
        jsondata["email"] = [email]

    result = _store(
        ctx,
        _write_category("person"),
        jsondata,
        "Created by osw task create-person",
    )
    return {
        "title": result["titles"][0],
        "url": result["urls"][0],
        "uuid": person_uuid,
        "change_id": result["change_id"],
        "titles": result["titles"],
        "urls": result["urls"],
    }
