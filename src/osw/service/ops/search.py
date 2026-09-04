"""Search and query operations: semantic (SMW ask), full-text, instances, SPARQL."""

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

    The query uses SMW ask syntax, e.g. ``[[Category:Item]]`` or
    ``[[Category:Item]][[Keyword::sensor]]``. Returns full page titles.
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
def full_text_search(ctx: Context, text: str, limit: Optional[int] = None) -> dict:
    """Prefix/full-text search for pages whose title matches ``text``."""
    lim = ctx.limit(limit)
    titles = ctx.osw.site.prefix_search(WtSite.SearchParam(query=text, limit=lim))
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

    ``category`` is a full category page name, e.g. ``Category:Item``.
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
    override. Returns ``{vars, bindings, count, truncated}``.
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
