"""Search and query tools: semantic (SMW ask), full-text, instances, SPARQL."""

from __future__ import annotations

from typing import Optional

from osw.core import OSW
from osw.sparql_client_smw import SmwSparqlClient
from osw.wtsite import WtSite

from .. import config
from ..connection import run_guarded
from ..serialization import cap_list, to_jsonable


def register(mcp) -> None:
    """Register read-only search/query tools on ``mcp``."""
    settings = config.get_settings()

    @mcp.tool()
    def search_entities(ask_query: str, limit: Optional[int] = None) -> dict:
        """Run a Semantic MediaWiki 'ask' query and return matching page titles.

        The query uses SMW ask syntax, e.g. ``[[Category:Item]]`` or
        ``[[Category:Item]][[Keyword::sensor]]``. Returns full page titles.
        """
        lim = limit or settings.max_results

        def _run(osw):
            titles = osw.site.semantic_search(
                WtSite.SearchParam(query=ask_query, limit=lim)
            )
            capped, total, truncated = cap_list(titles, lim)
            return {"titles": capped, "count": total, "truncated": truncated}

        return run_guarded(_run)

    @mcp.tool()
    def full_text_search(text: str, limit: Optional[int] = None) -> dict:
        """Prefix/full-text search for pages whose title matches ``text``."""
        lim = limit or settings.max_results

        def _run(osw):
            titles = osw.site.prefix_search(WtSite.SearchParam(query=text, limit=lim))
            capped, total, truncated = cap_list(titles, lim)
            return {"titles": capped, "count": total, "truncated": truncated}

        return run_guarded(_run)

    @mcp.tool()
    def list_instances_of_category(category: str, limit: Optional[int] = None) -> dict:
        """List full page titles of all instances of a category.

        ``category`` is a full category page name, e.g. ``Category:Item``.
        """
        lim = limit or settings.max_results

        def _run(osw):
            titles = osw.query_instances(
                OSW.QueryInstancesParam(categories=category, limit=lim)
            )
            capped, total, truncated = cap_list(titles, lim)
            return {"titles": capped, "count": total, "truncated": truncated}

        return run_guarded(_run)

    @mcp.tool()
    def sparql_query(
        query: str, endpoint: Optional[str] = None, limit: int = 500
    ) -> dict:
        """Run a raw SPARQL query against the instance's SPARQL endpoint.

        The endpoint defaults to ``OSW_SPARQL_ENDPOINT``; pass ``endpoint`` to
        override. Returns ``{vars, bindings, count, truncated}``.
        """
        ep = endpoint or settings.sparql_endpoint
        if not ep:
            return {
                "error": (
                    "SPARQL endpoint not configured. Set OSW_SPARQL_ENDPOINT "
                    "or pass the 'endpoint' argument."
                ),
                "type": "NotConfigured",
            }

        def _run(_osw):
            client = SmwSparqlClient(
                endpoint=ep,
                domain=settings.domain,
                auth="basic",
                user=settings.username,
                password=settings.password,
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

        return run_guarded(_run)
