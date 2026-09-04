"""Search operations: semantic (SMW ask), titles, content, instances, SPARQL."""

from __future__ import annotations

from typing import Optional

from osw.core import OSW
from osw.service import config, errors
from osw.service.context import Context
from osw.service.registry import operation
from osw.service.serialization import cap_list, to_jsonable
from osw.sparql_client_smw import SmwSparqlClient
from osw.wtsite import WtSite


@operation(
    group="search",
    cli_name="ask",
    read_only_hint=True,
    idempotent_hint=True,
)
def search_entities(ctx: Context, ask_query: str, limit: Optional[int] = None) -> dict:
    """Run a Semantic MediaWiki 'ask' query and return matching page titles.

    This is the only search that can find an entity by a property value, such
    as its name. OSW pages are titled by OSW-ID, for example
    ``Item:OSW7ec...``, so searching titles for a name finds nothing.

    The query uses SMW ask syntax. Examples:

    \b
      [[Category:Item]]
      [[Category:Item]][[Keyword::sensor]]
      [[Category:Item]][[HasName::~*sensor*]]

    ``~`` starts a wildcard comparison and ``*`` matches any text. Which
    property holds the name depends on the instance's schema: ``HasName``,
    ``Display_title_of`` and ``HasLabel`` are the usual candidates. Read the
    category schema (``osw schema get``) if a name query returns nothing.

    ``limit`` defaults to ``OSW_MAX_RESULTS`` (100 when that is unset).
    Returns ``{titles, count, truncated}``, where ``titles`` are full page
    names and ``count`` is how many the wiki returned.
    """
    lim = ctx.limit(limit)
    titles = ctx.osw.site.semantic_search(
        WtSite.SearchParam(query=ask_query, limit=lim)
    )
    capped, total, truncated = cap_list(titles, lim)
    return {"titles": capped, "count": total, "truncated": truncated}


@operation(
    group="search",
    cli_name="text",
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
    names and ``count`` is how many the wiki returned.
    """
    lim = ctx.limit(limit)
    titles = ctx.osw.site.prefix_search(WtSite.SearchParam(query=text, limit=lim))
    capped, total, truncated = cap_list(titles, lim)
    return {"titles": capped, "count": total, "truncated": truncated}


@operation(
    group="search",
    cli_name="content",
    read_only_hint=True,
    idempotent_hint=True,
)
def search_content(ctx: Context, text: str, limit: Optional[int] = None) -> dict:
    """Search the text content of pages for ``text``.

    Uses the MediaWiki ``search`` API, which reads page wikitext. On an OSW
    instance an entity's data lives in JSON slots, so a value stored as
    structured data may not be reachable here; ``osw search ask`` queries
    that data directly and is the better tool for it.

    Returns page titles, not the matching passages. ``limit`` defaults to
    ``OSW_MAX_RESULTS`` (100 when that is unset). Returns
    ``{titles, count, truncated}``, where ``titles`` are full page names
    and ``count`` is how many the wiki returned.
    """
    lim = ctx.limit(limit)
    titles = ctx.osw.site.content_search(WtSite.SearchParam(query=text, limit=lim))
    capped, total, truncated = cap_list(titles, lim)
    return {"titles": capped, "count": total, "truncated": truncated}


@operation(
    group="search",
    cli_name="instances",
    read_only_hint=True,
    idempotent_hint=True,
)
def list_instances_of_category(
    ctx: Context, category: str, limit: Optional[int] = None
) -> dict:
    """List full page titles of all instances of a category.

    ``category`` is a full category page name, e.g. ``Category:Item`` or
    ``Category:OSW...``. This runs the ask query
    ``[[HasType::Category:<category>]]``, so it lists the pages that declare
    this exact category as their type.

    ``limit`` defaults to ``OSW_MAX_RESULTS`` (100 when that is unset).
    Returns ``{titles, count, truncated}``, where ``titles`` are full page
    names and ``count`` is how many the wiki returned.
    """
    lim = ctx.limit(limit)
    titles = ctx.osw.query_instances(
        OSW.QueryInstancesParam(categories=category, limit=lim)
    )
    capped, total, truncated = cap_list(titles, lim)
    return {"titles": capped, "count": total, "truncated": truncated}


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
