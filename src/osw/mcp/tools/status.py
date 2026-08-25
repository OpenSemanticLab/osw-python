"""Status / whoami tool: report connection and configuration (no secrets)."""

from __future__ import annotations

import sys

from osw.service import config

from ..connection import get_ledger, osw_guard


def _osw_version():
    try:
        from importlib.metadata import version

        return version("osw")
    except Exception:
        return None


def register(mcp) -> None:
    """Register the read-only status tool on ``mcp``."""

    @mcp.tool()
    def status() -> dict:
        """Report the active instance, user, mode and ledger info.

        Performs a light connectivity check, but only when an instance is
        selected. Never returns the password.
        """
        settings = config.get_settings()
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
                "No OSL instance selected. Call select_instance to choose "
                f"one; available: {available}."
            )
            return info
        ledger = get_ledger()
        info["ledger_path"] = str(ledger.path)
        info["ledger_entry_count"] = ledger.entry_count()
        info["osw_version"] = _osw_version()
        try:
            with osw_guard():
                info["connected"] = True
        except Exception as exc:
            print(
                f"[osw-mcp] status connection check failed: {exc!r}",
                file=sys.stderr,
            )
            info["connected"] = False
            info["connection_error"] = str(exc)
        return info
