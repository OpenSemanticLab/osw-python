"""Status / whoami operation: report connection and configuration (no secrets)."""

from __future__ import annotations

import sys

from osw.service import config
from osw.service.context import Context
from osw.service.registry import operation


def _osw_version():
    try:
        from importlib.metadata import version

        return version("osw")
    except Exception:
        return None


@operation(group=None, read_only_hint=True, idempotent_hint=True)
def status(ctx: Context) -> dict:
    """Report the active instance, user, mode and ledger info.

    Performs a light connectivity check, but only when an instance is
    selected. Never returns the password.
    """
    settings = ctx.settings
    active_iri = config.get_active_iri()
    active_domain = config.get_active_domain()
    info = {
        **settings.redacted(),
        "active_iri": active_iri,
        "active_domain": active_domain,
    }
    if active_iri is None:
        available = ", ".join(config.available_iris()) or "(none)"
        info["connected"] = False
        info["message"] = (
            "No OSL instance selected. For a server process, set OSW_DOMAIN "
            "(or OSW_ENV_FILE to point at a .env file that sets it); for the "
            f"CLI, pass --instance <iri>. Available: {available}."
        )
        return info
    ledger = ctx.ledger
    info["ledger_entry_count"] = ledger.entry_count()
    info["osw_version"] = _osw_version()
    try:
        with ctx.guard():
            _ = ctx.osw
            info["connected"] = True
    except Exception as exc:
        print(
            f"[osw-mcp] status connection check failed: {exc!r}",
            file=sys.stderr,
        )
        info["connected"] = False
        info["connection_error"] = str(exc)
    return info
