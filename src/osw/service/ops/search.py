"""Search operations: semantic (SMW ask), titles, content, entities, SPARQL."""

from __future__ import annotations

from typing import List, Optional

from osw.core import OSW
from osw.service import config, errors
from osw.service.context import Context
from osw.service.registry import operation
from osw.service.serialization import cap_list, to_jsonable
from osw.sparql_client_smw import SmwSparqlClient
from osw.wiki_tools import _ask_results_as_dict, get_query_limit
from osw.wtsite import WtSite


def _hit_limit(total: int, limit: Optional[int]) -> bool:
    """Whether a result set is as large as the limit that produced it.

    The wiki applies the limit itself, so ``cap_list`` never has to cut these
    results and its own flag stays False. A full result set is then the only
    signal left that the wiki may hold further matches. ``limit=0`` asks for
    no results, so meeting it says nothing about truncation.
    """
    return bool(limit) and total >= limit


def _check_injection(value: str, field: str) -> None:
    """Reject a value that could change an ask query's structure."""
    if "]]" in value or "[[" in value or "|" in value:
        raise errors.ValidationError(f"{field} must not contain ']]', '[[' or '|'.")


@operation(
    group="search",
    cli_name="ask",
    read_only_hint=True,
    idempotent_hint=True,
    max_result_size_chars=200_000,
)
def search_ask(
    ctx: Context,
    ask_query: str,
    limit: Optional[int] = None,
    printouts: Optional[List[str]] = None,
) -> dict:
    """Run a Semantic MediaWiki 'ask' query and return matching page titles.

    This is the only search that can find an entity by a property value, such
    as its name. OSW pages are titled by OSW-ID, for example
    ``Item:OSW7ec...``, so searching titles for a name finds nothing.

    The query uses SMW ask syntax. Examples:

    \b
      [[Category:Item]]
      [[Category:Item]][[Keyword::sensor]]
      [[Category:Item]][[HasName::~*sensor*]]

    ``~`` starts a wildcard comparison and ``*`` matches any text.

    Which property holds a name depends on the schema. The shipped base
    schema maps the JSON field ``label`` to ``Property:HasLabel`` and
    ``name`` to ``Property:HasName``, and stored queries read the displayed
    label as ``Display_title_of``. A category declares this mapping in the
    ``@context`` of its schema, so read it with ``osw schema get`` when a
    name query returns nothing.

    ``limit`` defaults to ``OSW_MAX_RESULTS`` (100 when that is unset). A
    ``limit=N`` written into the query itself wins over it.

    ``printouts`` requests SMW property values alongside each hit, so a
    caller does not have to follow up with one ``entity get`` per title.
    Give bare property names, such as ``HasStatus``, without the
    ``Property:`` prefix; use ``osw schema props`` to discover a category's
    property names. Requesting a property the category does not define does
    not raise - the row simply carries that key set to ``null``.
    ``Display_title_of`` does not work as a printout: its printout key comes
    back translated into the wiki's content language regardless of the
    alias, so it always resolves to ``null`` here - read an entity's label
    from its title or with ``entity get`` instead. When ``printouts`` is
    omitted or empty, the query and result are exactly as without it.

    Returns ``{titles, count, truncated}``, where ``titles`` are full page
    names, ``count`` is how many came back once hits whose page does not
    exist were dropped, and ``truncated`` reports that further matches may
    exist beyond them. When ``printouts`` is given, the result also carries
    ``rows``: a list of ``{title, printouts}`` in the same order as
    ``titles``, where ``printouts`` maps each requested name to the raw
    value SMW returned for it - a page reference keeps its ``fulltext`` and
    ``fullurl`` rather than being flattened to a string.
    """
    lim = ctx.limit(limit)
    # semantic_search lets a 'limit=' written into the query win over `lim`,
    # so the flag has to compare against the limit that reached the wiki.
    query_limit = get_query_limit(ask_query)
    effective_limit = lim if query_limit is None else query_limit

    if not printouts:
        titles = ctx.osw.site.semantic_search(
            WtSite.SearchParam(query=ask_query, limit=lim)
        )
        # `titles` excludes hits whose page does not exist, so a result set
        # thinned that way reads as not truncated.
        capped, total, truncated = cap_list(titles, lim)
        return {
            "titles": capped,
            "count": total,
            "truncated": truncated or _hit_limit(total, effective_limit),
        }

    # The '=name' alias forces the printout key in the result to the property
    # name; without it, SMW keys the result by the property's display label,
    # which need not equal the property name, and the row values below are
    # looked up by name.
    full_query = ask_query + "".join(f"|?{p}={p}" for p in printouts)
    raw = ctx.osw.site.semantic_search(
        WtSite.SearchParam(query=full_query, limit=lim, return_json=True)
    )
    response = raw[0] if raw else {}
    payload = _ask_results_as_dict(response.get("query", {}).get("results", {}))
    hits = [p for p in payload.values() if p.get("exists") == "1"]
    capped_hits, total, truncated = cap_list(hits, lim)
    rows = [
        {
            "title": hit["fulltext"],
            "printouts": {p: hit.get("printouts", {}).get(p) for p in printouts},
        }
        for hit in capped_hits
    ]
    return {
        "titles": [row["title"] for row in rows],
        "count": total,
        "truncated": truncated or _hit_limit(total, effective_limit),
        "rows": rows,
    }


@operation(
    group="search",
    cli_name="titles",
    read_only_hint=True,
    idempotent_hint=True,
)
def search_titles(ctx: Context, text: str, limit: Optional[int] = None) -> dict:
    """Search page titles by prefix. This does not search page content.

    Matches pages whose title starts with ``text``, via the MediaWiki
    ``prefixsearch`` API. OSW pages are titled by OSW-ID, for example
    ``Item:OSW7ec...``, so an entity's name is not part of its title and
    cannot be found here. Use ``osw search ask`` to search by name.
    Use ``osw search content`` to search the text of pages.

    Useful for the titles that are readable: categories, properties,
    templates and other schema pages.

    ``limit`` defaults to ``OSW_MAX_RESULTS`` (100 when that is unset).
    Returns ``{titles, count, truncated}``, where ``titles`` are full page
    names, ``count`` is how many the wiki returned and ``truncated`` reports
    that further matches may exist beyond them.
    """
    lim = ctx.limit(limit)
    titles = ctx.osw.site.prefix_search(WtSite.SearchParam(query=text, limit=lim))
    capped, total, truncated = cap_list(titles, lim)
    return {
        "titles": capped,
        "count": total,
        "truncated": truncated or _hit_limit(total, lim),
    }


@operation(
    group="search",
    cli_name="content",
    read_only_hint=True,
    idempotent_hint=True,
)
def search_content(ctx: Context, text: str, limit: Optional[int] = None) -> dict:
    """Search the text content of pages for ``text``.

    Uses the MediaWiki ``search`` API, which reads page wikitext. On an OSW
    instance an entity's values live in its ``jsondata`` slot, not in the
    wikitext, so a stored value may not be reachable here; ``osw search ask``
    queries that data directly and is the better tool for it.

    Returns page titles, not the matching passages. ``limit`` defaults to
    ``OSW_MAX_RESULTS`` (100 when that is unset). Returns
    ``{titles, count, truncated}``, where ``titles`` are full page names,
    ``count`` is how many the wiki returned and ``truncated`` reports that
    further matches may exist beyond them.
    """
    lim = ctx.limit(limit)
    titles = ctx.osw.site.content_search(WtSite.SearchParam(query=text, limit=lim))
    capped, total, truncated = cap_list(titles, lim)
    return {
        "titles": capped,
        "count": total,
        "truncated": truncated or _hit_limit(total, lim),
    }


@operation(
    group="search",
    cli_name="entities",
    read_only_hint=True,
    idempotent_hint=True,
)
def search_entities(ctx: Context, category: str, limit: Optional[int] = None) -> dict:
    """List full page titles of all instances of a category.

    ``category`` is a full category page name, e.g. ``Category:Item`` or
    ``Category:OSW...``. This runs the ask query
    ``[[HasType::<category>]]``, so it lists the pages that declare
    this exact category as their type.

    ``limit`` defaults to ``OSW_MAX_RESULTS`` (100 when that is unset).
    Returns ``{titles, count, truncated}``, where ``titles`` are full page
    names, ``count`` is how many the wiki returned and ``truncated`` reports
    that further matches may exist beyond them.
    """
    lim = ctx.limit(limit)
    titles = ctx.osw.query_instances(
        OSW.QueryInstancesParam(categories=category, limit=lim)
    )
    capped, total, truncated = cap_list(titles, lim)
    return {
        "titles": capped,
        "count": total,
        "truncated": truncated or _hit_limit(total, lim),
    }


@operation(
    group="search",
    cli_name="sparql",
    read_only_hint=True,
    idempotent_hint=True,
    open_world_hint=True,
    max_result_size_chars=200_000,
)
def sparql_query(
    ctx: Context, query: str, endpoint: Optional[str] = None, limit: int = 500
) -> dict:
    """Run a raw SPARQL query against the instance's SPARQL endpoint.

    The endpoint defaults to ``OSW_SPARQL_ENDPOINT``; pass ``endpoint`` to
    override. If neither is set the command fails.

    ``limit`` caps the returned bindings and defaults to 500. It is applied
    to the response, not added to the query, so a large query still costs the
    endpoint its full work.

    Returns ``{vars, bindings, count, truncated}``, where ``count`` is how
    many bindings the endpoint returned.
    """
    ep = endpoint or ctx.settings.sparql_endpoint
    if not ep:
        raise errors.NotConfigured(
            "SPARQL endpoint not configured. Set OSW_SPARQL_ENDPOINT "
            "or pass the 'endpoint' argument."
        )

    username, password = config.get_active_credentials()
    client = SmwSparqlClient(
        endpoint=ep,
        domain=config.get_active_domain(),
        auth="basic",
        user=username,
        password=password,
    )
    raw = client.sparqlQuery(query)
    bindings = raw.get("results", {}).get("bindings", [])
    capped, total, truncated = cap_list(bindings, limit)
    return {
        "vars": raw.get("head", {}).get("vars", []),
        "bindings": to_jsonable(capped),
        "count": total,
        "truncated": truncated,
    }


@operation(
    group="search",
    cli_name="label",
    read_only_hint=True,
    idempotent_hint=True,
)
def search_by_label(
    ctx: Context,
    label: str,
    category: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    """Find an entity by its exact display label.

    Runs the ask query ``[[Display_title_of::<label>]]``, matching the page's
    displayed title exactly - not a substring or fuzzy match. Works for
    ``Category:`` pages too, since a category is displayed under its own
    OSW-ID title like any other entity; this is the way to find a category's
    OSW-ID from its human-readable name. Pass ``category`` (with or without
    the ``Category:`` prefix) to narrow the search to instances of one
    category.

    Returns titles only, the same ``{titles, count, truncated}`` shape as
    the other search operations. Pair this with ``search ask --printouts``
    (or ``entity get``) when you need property values, not just the title.
    """
    _check_injection(label, "label")
    query = f"[[Display_title_of::{label}]]"
    if category is not None:
        _check_injection(category, "category")
        cat = category if category.startswith("Category:") else f"Category:{category}"
        query = f"[[{cat}]]" + query

    lim = ctx.limit(limit)
    titles = ctx.osw.site.semantic_search(WtSite.SearchParam(query=query, limit=lim))
    capped, total, truncated = cap_list(titles, lim)
    return {
        "titles": capped,
        "count": total,
        "truncated": truncated or _hit_limit(total, lim),
    }
