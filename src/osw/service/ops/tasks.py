"""Task management operations: create/update/list tasks, projects, persons.

Narrow, field-based operations for OSL task management, built on three OSL
core categories (Task, Person, Project). Every operation takes plain typed
parameters and returns a small flat dict, so an agent driving this spends few
tokens; no JSON Schema is ever handed to the caller.
"""

from __future__ import annotations

import re
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

# SMW property names, read from the @context of the Process and Task schemas
# on arkeve. The JSON field name and the SMW property name differ, so
# queries must use the property name.
PROP_STATUS = "HasStatus"
PROP_PRIO = "HasPriority"
PROP_RELATED_TO = "IsRelatedTo"
PROP_ACTIONEE = "HasActionee"
PROP_LABEL = "HasLabel"

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


def _ask_rows(
    ctx: Context, query: str, printouts: list[str], limit: Optional[int] = None
) -> tuple[list[dict], bool]:
    """Run an SMW ask query that returns property values, not only titles."""
    lim = ctx.limit(limit)
    full = query + "".join(f"|?{p}" for p in printouts)
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


def _page_values(row: dict, prop: str) -> list[dict]:
    """Return [{"title": ..., "label": ...}, ...] from one page-valued printout."""
    entries = row.get("printouts", {}).get(prop) or []
    return [
        {"title": e["fulltext"], "label": e.get("displaytitle") or e["fulltext"]}
        for e in entries
    ]


def _first_page_value(row: dict, prop: str) -> Optional[dict]:
    """The first entry of ``_page_values``, or ``None``."""
    values = _page_values(row, prop)
    return values[0] if values else None


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
    rows, _ = _ask_rows(
        ctx, f"[[{category}]][[{PROP_LABEL}::~*{value}*]]", [], limit=10
    )
    if len(rows) == 1:
        return rows[0]["fulltext"]
    if not rows:
        list_op = "list_projects" if kind == "project" else "list_persons"
        raise errors.NotFound(
            f"No {kind} matches '{value}'. Use '{list_op}' to see candidates."
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


def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|")


def _render_markdown(tasks: list[dict]) -> str:
    """Render ``list_tasks``' tasks as a Markdown table.

    The single rendering function for tasks; both ``list_tasks(markdown=True)``
    and ``render_task_view`` call it and nothing else renders tasks.
    """
    lines = [
        "| Task | Status | Priority | Project | Actionees |",
        "| --- | --- | --- | --- | --- |",
    ]
    for task in tasks:
        task_cell = f"[{_escape_cell(task['label'])}]({task['url']})"
        status_cell = _escape_cell(task["status"] or "")
        prio_cell = _escape_cell(task["prio"] or "")
        project_cell = _escape_cell("; ".join(p["label"] for p in task["related_to"]))
        actionees_cell = _escape_cell("; ".join(a["label"] for a in task["actionees"]))
        lines.append(
            f"| {task_cell} | {status_cell} | {prio_cell} | {project_cell} | "
            f"{actionees_cell} |"
        )
    return "\n".join(lines)


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

    Use ``list_tasks`` filtered by ``project`` first as a duplicate check: an
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
    read the current actionees with ``list_tasks`` and pass the full list.

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
    cli_name="list",
    read_only_hint=True,
    idempotent_hint=True,
)
def list_tasks(
    ctx: Context,
    project: Optional[str] = None,
    actionee: Optional[str] = None,
    status: Optional[str] = None,
    text: Optional[str] = None,
    mine: bool = False,
    markdown: bool = False,
    limit: Optional[int] = None,
) -> dict:
    """List tasks, filtered by project, actionee, status and/or label text.

    This is also the duplicate check before creating a task: filter by
    ``project`` and compare each returned ``label`` against the label you
    are about to create; an exact label match within one project means the
    task already exists. ``project`` and ``actionee`` accept a page name or
    a label to look up. ``mine=True`` filters to the configured
    ``OSW_PERSON_IRI`` and cannot be combined with ``actionee``.

    Returns ``{tasks, count, truncated}``, plus ``markdown`` when
    ``markdown=True``. Each task is
    ``{title, url, label, status, prio, related_to, actionees}``, where
    ``status``/``prio`` are the human labels or ``None`` and
    ``related_to``/``actionees`` are lists of ``{title, label}``.
    """
    if mine and actionee is not None:
        raise errors.ValidationError("Pass either 'mine' or 'actionee', not both.")

    query = f"[[{CATEGORY_TASK}]]"
    person_iri = None
    if project is not None:
        project_title = _resolve_ref(ctx, project, CATEGORY_PROJECT, "project")
        query += f"[[{PROP_RELATED_TO}::{project_title}]]"
    if mine:
        settings = config.get_settings()
        if not settings.person_iri:
            raise errors.NotConfigured(
                "OSW_PERSON_IRI is not configured; it is required to filter "
                "tasks assigned to you."
            )
        person_iri = settings.person_iri
        query += f"[[{PROP_ACTIONEE}::{person_iri}]]"
    elif actionee is not None:
        actionee_title = _resolve_ref(ctx, actionee, CATEGORY_PERSON, "person")
        query += f"[[{PROP_ACTIONEE}::{actionee_title}]]"
    if status is not None:
        status_title = _resolve_vocab(status, STATUS_ITEMS, STATUS_ALIASES, "status")
        query += f"[[{PROP_STATUS}::{status_title}]]"
    if text is not None:
        _check_injection(text, "text")
        query += f"[[{PROP_LABEL}::~*{text}*]]"

    rows, truncated = _ask_rows(
        ctx, query, [PROP_STATUS, PROP_PRIO, PROP_RELATED_TO, PROP_ACTIONEE], limit
    )
    # A typo in the configured page name gives the same empty result as having
    # no tasks, so tell the two apart. The extra read only happens when the
    # result is empty.
    if person_iri and not rows and not _get_page_uncached(ctx, person_iri).exists:
        raise errors.NotConfigured(
            f"OSW_PERSON_IRI is set to '{person_iri}', which is not a page on "
            "this wiki, so no task can reference it. Use 'list_persons' to "
            "find the right page name."
        )
    tasks = []
    for row in rows:
        status_value = _first_page_value(row, PROP_STATUS)
        prio_value = _first_page_value(row, PROP_PRIO)
        tasks.append({
            "title": row["fulltext"],
            "url": row["fullurl"],
            "label": _label_of(row),
            "status": status_value["label"] if status_value else None,
            "prio": prio_value["label"] if prio_value else None,
            "related_to": _page_values(row, PROP_RELATED_TO),
            "actionees": _page_values(row, PROP_ACTIONEE),
        })
    result = {"tasks": tasks, "count": len(tasks), "truncated": truncated}
    if markdown:
        result["markdown"] = _render_markdown(tasks)
    return result


@operation(
    group="task",
    cli_name="list-projects",
    read_only_hint=True,
    idempotent_hint=True,
)
def list_projects(
    ctx: Context, text: Optional[str] = None, limit: Optional[int] = None
) -> dict:
    """List projects, optionally filtered by label text.

    Use this to find a project's page name for ``create_task``'s
    ``project`` parameter when a label match would be ambiguous.

    Returns ``{projects, count, truncated}`` where each entry is
    ``{title, url, label}``.
    """
    query = f"[[{CATEGORY_PROJECT}]]"
    if text is not None:
        _check_injection(text, "text")
        query += f"[[{PROP_LABEL}::~*{text}*]]"
    rows, truncated = _ask_rows(ctx, query, [], limit)
    projects = [
        {"title": r["fulltext"], "url": r["fullurl"], "label": _label_of(r)}
        for r in rows
    ]
    return {"projects": projects, "count": len(projects), "truncated": truncated}


@operation(
    group="task",
    cli_name="list-persons",
    read_only_hint=True,
    idempotent_hint=True,
)
def list_persons(
    ctx: Context, text: Optional[str] = None, limit: Optional[int] = None
) -> dict:
    """List persons, optionally filtered by label text.

    Finds persons stored in subclasses too, because it queries category
    membership rather than an exact type match. Search here before calling
    ``create_person``; most instances already hold every person you need.

    Returns ``{persons, count, truncated}`` where each entry is
    ``{title, url, label}``.
    """
    query = f"[[{CATEGORY_PERSON}]]"
    if text is not None:
        _check_injection(text, "text")
        query += f"[[{PROP_LABEL}::~*{text}*]]"
    rows, truncated = _ask_rows(ctx, query, [], limit)
    persons = [
        {"title": r["fulltext"], "url": r["fullurl"], "label": _label_of(r)}
        for r in rows
    ]
    return {"persons": persons, "count": len(persons), "truncated": truncated}


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
    already holds every person you need. Search with ``list_persons`` first,
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


@operation(
    group="task",
    cli_name="render",
    surfaces=frozenset({"cli"}),
    read_only_hint=True,
)
def render_task_view(
    ctx: Context,
    output_path: str,
    project: Optional[str] = None,
    actionee: Optional[str] = None,
    status: Optional[str] = None,
    mine: bool = False,
    limit: Optional[int] = None,
) -> dict:
    """Render a Markdown table of tasks and write it to a local file.

    CLI only, since ``output_path`` names a local file and the MCP surface
    never exposes a path. Filters are the same as ``list_tasks``.

    Returns ``{output_path, count, bytes_written}``.
    """
    result = list_tasks(
        ctx,
        project=project,
        actionee=actionee,
        status=status,
        mine=mine,
        markdown=True,
        limit=limit,
    )
    content = result["markdown"]
    data = content.encode("utf-8")
    with open(output_path, "w", encoding="utf-8") as stream:
        stream.write(content)
    return {
        "output_path": output_path,
        "count": result["count"],
        "bytes_written": len(data),
    }
