"""Instance selection tools: list and switch between configured OSL instances.

A server can be configured with several candidate instances (an env-configured
domain and/or the iris in a credential file, see :mod:`osw.mcp.config`). These
tools let the model discover the available instances and pick which one
subsequent tool calls talk to. Registered unconditionally, not gated on
``include_writes``: they change server-local state, not wiki content.
"""

from __future__ import annotations

from .. import config, connection


def register(mcp) -> None:
    """Register the instance-selection tools on ``mcp``."""

    @mcp.tool()
    def list_instances() -> dict:
        """List the OSL instances this server can connect to.

        Reports the iris available from the env-configured domain and/or a
        configured credential file, and which one (if any) is currently
        active. Never returns usernames, passwords, or any credential value.
        """
        return {
            "iris": config.available_iris(),
            "active_iri": config.get_active_iri(),
            "active_domain": config.get_active_domain(),
        }

    @mcp.tool()
    def select_instance(iri: str) -> dict:
        """Select the OSL instance subsequent tool calls should talk to.

        ``iri`` must be one of the iris returned by ``list_instances``.
        Rebuilds the shared connection and provenance ledger so a stale
        instance is never reused, but does not connect eagerly; the next
        tool call connects to the newly selected instance.
        """
        try:
            config.set_active_instance(iri)
        except ValueError as exc:
            return {"error": str(exc), "type": "UnknownInstance"}
        connection.reset()
        return {
            "active_iri": config.get_active_iri(),
            "active_domain": config.get_active_domain(),
        }
