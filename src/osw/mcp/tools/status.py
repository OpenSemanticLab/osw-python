"""Status / whoami tool: report connection and configuration (no secrets)."""

from __future__ import annotations

import sys

from .. import config
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
        """Report the connected domain, user, mode and ledger info.

        Performs a light connectivity check. Never returns the password.
        """
        settings = config.get_settings()
        ledger = get_ledger()
        info = {
            **settings.redacted(),
            "ledger_path": str(ledger.path),
            "ledger_entry_count": ledger.entry_count(),
            "osw_version": _osw_version(),
        }
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
