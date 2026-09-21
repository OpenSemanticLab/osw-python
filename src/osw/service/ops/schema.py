"""Schema introspection: fetch a category's JSON Schema so the model can build
valid entities before writing them."""

from __future__ import annotations

import json

from osw.service import errors
from osw.service.context import Context
from osw.service.registry import operation
from osw.service.serialization import maybe_truncate
from osw.wiki_tools import _ask_results_as_dict
from osw.wtsite import WtSite


def _merge_schema(
    ctx: Context,
    title: str,
    max_depth: int,
    merged: dict,
    sources: list[str],
    seen: set,
    skipped: list,
) -> None:
    """Merge one page's own JSON Schema into ``merged``, then recurse into
    its parents.

    Mirrors ``WtSite._merge_jsonld_context``'s parent-first walk. ``title``
    is a full page title (``Category:...`` or ``JsonSchema:...``); a
    ``Category:`` page keeps its schema in the ``jsonschema`` slot, a
    ``JsonSchema:`` page in the ``main`` slot. Parent references come from
    string entries of the schema's ``@context`` list and from ``$ref``
    values inside ``allOf``. Recursion visits parents before this page
    applies its own values, so a child's own value always wins on conflict.
    A page that cannot be read, or whose slot does not parse, is skipped
    rather than aborting the walk; each skip is appended to ``skipped`` as
    ``{"title": ..., "reason": ...}``, unless the page was already ``seen``,
    since reaching the same page twice through two parents is a normal
    diamond in the category graph, not a failure. ``seen`` also stops the
    same page being read twice within one call, which breaks a cycle.
    """
    if title in seen:
        return
    if max_depth <= 0:
        skipped.append({"title": title, "reason": "maximum depth reached"})
        return
    seen.add(title)

    try:
        page = ctx.get_page_uncached(title)
        if not page.exists:
            skipped.append({"title": title, "reason": "page does not exist"})
            return
        if "JsonSchema:" in title:
            schema = page.get_slot_content("main")
        else:
            schema = page.get_slot_content("jsonschema")
        if isinstance(schema, str) and not schema.strip():
            schema = None
        if schema is None:
            skipped.append({"title": title, "reason": "no schema slot"})
            return
        if isinstance(schema, str):
            schema = json.loads(schema)
    except Exception as exc:
        skipped.append({"title": title, "reason": f"could not be read: {exc}"})
        return
    if not isinstance(schema, dict):
        skipped.append({"title": title, "reason": "schema slot is not a JSON object"})
        return
    sources.append(title)

    parents: list[str] = []
    context = schema.get("@context")
    entries = context if isinstance(context, list) else ([context] if context else [])
    for entry in entries:
        if isinstance(entry, str):
            parents.append(entry)
    for ref in schema.get("allOf", []) or []:
        if isinstance(ref, dict) and ref.get("$ref"):
            parents.append(ref["$ref"])

    for ref in parents:
        parent_title = ref.split("/wiki/")[-1].split("?")[0]
        if parent_title.startswith("Category:") or parent_title.startswith(
            "JsonSchema:"
        ):
            _merge_schema(
                ctx, parent_title, max_depth - 1, merged, sources, seen, skipped
            )

    # Apply this page's own schema last, so it overrides its parents:
    # properties and definitions merge per key (this page wins on conflict),
    # required is a de-duplicated union in first-seen order, and every other
    # top-level key is simply taken from this page.
    properties = {**merged.get("properties", {}), **schema.get("properties", {})}
    required = list(
        dict.fromkeys([*merged.get("required", []), *schema.get("required", [])])
    )
    definitions = {**merged.get("definitions", {}), **schema.get("definitions", {})}
    merged.update(schema)
    merged["properties"] = properties
    merged["required"] = required
    merged["definitions"] = definitions


def _resolve_schema(ctx: Context, category: str, max_depth: int = 10) -> tuple:
    """Resolve ``category``'s effective JSON Schema across its parent chain.

    A category's ``jsonschema`` slot only ever declares its own properties
    and points at its parent, so this walks the same chain
    ``WtSite.get_jsonld_context`` does and merges each level, parent first.
    No result is cached: each call may read several pages, which keeps the
    result fresh when a category page is edited.

    Returns ``(merged_schema, sources, skipped)``, where ``sources`` lists the
    full titles of every page successfully read, in the order visited, and
    ``skipped`` lists every page the walk could not use, each as
    ``{"title", "reason"}``, in the order visited.
    """
    merged: dict = {}
    sources: list[str] = []
    skipped: list = []
    _merge_schema(ctx, category, max_depth, merged, sources, set(), skipped)

    # A page can be recorded as depth-exhausted on one branch and then read
    # successfully on a shorter one, and the same page can exhaust the depth
    # on two branches. Neither should reach the caller, so reconcile the two
    # lists here rather than complicating the walk.
    sources_seen = set(sources)
    reconciled: list = []
    reconciled_titles: set = set()
    for entry in skipped:
        title = entry["title"]
        if title in sources_seen or title in reconciled_titles:
            continue
        reconciled_titles.add(title)
        reconciled.append(entry)
    return merged, sources, reconciled


@operation(
    group="schema",
    cli_name="get",
    read_only_hint=True,
    idempotent_hint=True,
    max_result_size_chars=200_000,
)
def get_category_schema(ctx: Context, category: str, resolve: bool = False) -> dict:
    """Return the JSON Schema of a category (its ``jsonschema`` slot).

    ``category`` is a full category page name, e.g. ``Category:Item``. The
    schema is read directly from the page slot, which - unlike fetching and
    generating models - does not modify any local files. Use the returned
    schema to construct a valid ``jsondata`` payload for
    ``create_or_update_entity``.

    Without ``resolve`` (the default), the schema covers one level only: a
    category's own ``jsonschema`` slot, not what it inherits from its
    parents. Since an OSL category inherits most of its properties from its
    parent chain, the one-level schema is usually not enough on its own to
    build a valid payload, even though that is what it is for. Pass
    ``resolve=True`` to walk the parent chain and merge it into one schema -
    a child's own property always wins over a parent's - which is what
    ``create_or_update_entity`` actually needs. The resolved result gains
    ``resolved: true`` and a ``sources`` list of every page title
    successfully read while resolving it, in the order visited. It also
    gains a ``skipped`` list naming every page the walk visited and could
    not use, and why - the walk's depth limit was reached, the page does
    not exist, it has no schema slot, it could not be read, or its slot did
    not parse. A non-empty ``skipped`` means the merged schema may be
    missing properties those pages would have contributed.
    """
    page = ctx.get_page_uncached(category)
    if not page.exists:
        return {"category": category, "exists": False, "schema": None}
    if not resolve:
        schema = page.get_slot_content("jsonschema")
        content, truncated = maybe_truncate(schema, ctx.settings.max_chars)
        return {
            "category": category,
            "exists": True,
            "schema": content,
            "truncated": truncated,
        }
    merged, sources, skipped = _resolve_schema(ctx, category)
    content, truncated = maybe_truncate(merged, ctx.settings.max_chars)
    return {
        "category": category,
        "exists": True,
        "schema": content,
        "truncated": truncated,
        "resolved": True,
        "sources": sources,
        "skipped": skipped,
    }


@operation(
    group="schema",
    cli_name="props",
    read_only_hint=True,
    idempotent_hint=True,
)
def get_category_property_map(ctx: Context, category: str) -> dict:
    """Return the Semantic MediaWiki property name for each of a category's fields.

    These are the names to use in an SMW ``ask`` query and in the
    ``printouts`` parameter of ``search ask`` - for example, the JSON field
    ``status`` typically maps to the property ``HasStatus``. The mapping is
    one-way and cannot be inverted: several JSON fields may share one
    property. Returned names carry no ``Property:`` prefix.

    Every OSL category chain reaches Entity, which declares at least a
    label mapping, so an empty map is never a genuinely property-less
    category; it means ``category``'s page is missing or unreadable, or
    that ``category`` does not actually name a category. Rather than
    returning that as a false-looking empty success, this raises
    ``errors.SchemaError`` naming ``category``.
    """
    properties = ctx.osw.site.get_smw_property_map(category)
    if not properties:
        raise errors.SchemaError(
            f"'{category}' declares no Semantic MediaWiki properties: its "
            "page is missing or unreadable, or 'category' does not name a "
            "real category."
        )
    return {
        "category": category,
        "properties": properties,
        "count": len(properties),
    }


MAX_FIELD_USAGE_SAMPLE = 100


def _check_injection(value: str, field: str) -> None:
    """Reject a value that could change an ask query's structure.

    A private copy: ``ops.search`` keeps its own.
    """
    if "]]" in value or "[[" in value or "|" in value:
        raise errors.ValidationError(f"{field} must not contain ']]', '[[' or '|'.")


def _is_populated(value) -> bool:
    """Whether a stored ``jsondata`` value counts as filled in.

    Only an absent value is empty: ``None``, ``""``, ``[]`` and ``{}``.
    ``False`` and ``0`` are values a field genuinely holds, so a plain
    falsy test would undercount them.
    """
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True


@operation(
    group="schema",
    cli_name="usage",
    read_only_hint=True,
    idempotent_hint=True,
)
def get_field_usage(ctx: Context, category: str, sample: int = 20) -> dict:
    """Report which of a category's declared fields real instances populate.

    A category schema often declares several fields of the same shape for
    one idea: ``Category:Task`` on one instance declares ``related_to``,
    ``related_to_project``, ``belongs_to_project`` and ``projects``, all
    arrays of strings, and only one of them is used in practice. The schema
    alone cannot say which. Counting Semantic MediaWiki properties cannot
    say it either, because a category's ``@context`` maps several JSON
    fields onto one property name, so ``related_to`` and
    ``related_to_project`` both resolve to ``IsRelatedTo``. This operation
    therefore reads a sample of stored instances and counts, per top-level
    ``jsondata`` field, how many of them give that field a value.

    It reads one wiki page per sampled instance, which makes it slower than
    the other schema operations. ``sample`` is how many instances to read;
    it defaults to 20 and is capped at 100.

    The result describes the sampled instances only and may not represent
    every instance of the category. ``more_instances_exist`` tells the
    caller the sample was not the whole set, so a count of 0 there means
    unused among the instances read, not proven unused.

    The sampled instances are not drawn at random. The query returns them in
    the wiki's own order, and the same first ``sample`` of them come back
    every time, so raising ``sample`` extends the set rather than replacing
    it. That order appears to follow page creation, so a field that only
    recent instances use can show a count of 0. Raise ``sample`` before
    concluding that a field is unused.

    Instances are found with ``[[HasType::Category:<category>]]``, the same
    query ``search entities`` runs, so only pages declaring this exact
    category as their type are read. Instances of a subcategory are not.
    A category whose instances all declare a subcategory therefore reports
    ``sampled`` 0. That result supports no conclusion about field usage, so
    ``fields``, ``declared_unused`` and ``undeclared_present`` are all empty
    whenever ``sampled`` is 0. Query the subcategory instead.

    Returns ``{category, sampled, fields, declared_unused,
    undeclared_present, more_instances_exist, unreadable, skipped}``.
    ``sampled`` is how many instances were read and counted. ``fields``
    holds one ``{field, populated, declared}`` entry per declared property
    and per undeclared key seen in an instance, ordered by ``populated``
    descending, then by field name ascending. ``unreadable`` holds one
    ``{title, reason}`` entry per sampled instance whose page or ``jsondata``
    slot could not be read; those are not counted. Check it before trusting a
    low ``sampled``, since a connection failure and a deleted page both lower
    that number and only the reason tells them apart. ``skipped`` lists the
    schema pages the parent-chain walk could not use, as
    ``get_category_schema`` does.
    """
    if sample < 1 or sample > MAX_FIELD_USAGE_SAMPLE:
        raise errors.ValidationError(
            f"Invalid sample '{sample}'. It must be between 1 and "
            f"{MAX_FIELD_USAGE_SAMPLE}, since every sampled instance costs "
            "one page read."
        )
    _check_injection(category, "category")

    merged, _sources, skipped = _resolve_schema(ctx, category)
    declared = merged.get("properties") or {}
    if not declared:
        raise errors.SchemaError(
            f"'{category}' declares no properties: its page is missing or "
            "unreadable, or 'category' does not name a real category."
        )

    # The same ask query 'search entities' runs through OSW.query_instances,
    # here with return_json so the raw response carries SMW's truncation
    # marker. Unlike tasks._ask_rows this keeps every row rather than only
    # those whose 'exists' flag is "1": a title whose page really is gone is
    # recorded as unreadable below anyway.
    name = category.split(":")[-1]
    raw = ctx.osw.site.semantic_search(
        WtSite.SearchParam(
            query=f"[[HasType::Category:{name}]]",
            limit=sample,
            return_json=True,
        )
    )
    response = raw[0] if raw else {}
    # SMW serialises a result set as an object keyed by title, but an empty
    # one as an array. The shared normaliser also keys a non-empty array by
    # 'fulltext', so no row is dropped when that form appears.
    results = _ask_results_as_dict(response.get("query", {}).get("results", {}))
    titles = [
        row["fulltext"]
        for row in results.values()
        if isinstance(row, dict) and row.get("fulltext")
    ][:sample]
    more_instances_exist = "query-continue-offset" in response

    counts: dict = dict.fromkeys(declared, 0)
    unreadable: list = []
    sampled = 0
    for title in titles:
        # One bad page must not abort the whole sample, so anything that
        # does not yield a jsondata object is recorded and skipped.
        try:
            # Uncached, like the schema walk above: a write earlier in the
            # same process can leave the page cache enabled, and the cached
            # path would then count a revision from before that write.
            page = ctx.get_page_uncached(title)
            if not page.exists:
                reason = "page does not exist"
                jsondata = None
            else:
                jsondata = page.get_slot_content("jsondata")
                reason = (
                    "no jsondata slot"
                    if jsondata is None
                    else "jsondata slot is not a JSON object"
                )
        except Exception as exc:
            # The reason matters: an outage that hits every page produces the
            # same 'sampled' 0 as a category whose instances really are gone.
            jsondata, reason = None, f"could not be read: {exc}"
        if not isinstance(jsondata, dict):
            unreadable.append({"title": title, "reason": reason})
            continue
        sampled += 1
        for field, value in jsondata.items():
            counts.setdefault(field, 0)
            if _is_populated(value):
                counts[field] += 1

    fields = [
        {"field": field, "populated": count, "declared": field in declared}
        for field, count in counts.items()
    ]
    fields.sort(key=lambda entry: (-entry["populated"], entry["field"]))
    # With nothing read, every count would be 0, and a caller would take that
    # as 'no field is in use'. Zero observations support no such claim, so the
    # counted keys stay empty and 'sampled' carries the whole answer.
    if not sampled:
        fields = []
    return {
        "category": category,
        "sampled": sampled,
        "fields": fields,
        "declared_unused": (
            sorted(f for f in declared if counts[f] == 0) if sampled else []
        ),
        "undeclared_present": (
            sorted(f for f in counts if f not in declared) if sampled else []
        ),
        "more_instances_exist": more_instances_exist,
        "unreadable": sorted(unreadable, key=lambda entry: entry["title"]),
        "skipped": skipped,
    }
