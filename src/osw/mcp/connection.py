"""Shared, thread-safe connection to a live OSL instance.

A single process-wide ``OswExpress`` is built lazily on first use. Because
mwclient's session is not thread-safe and MCPServer runs synchronous tools in a
worker-thread pool, every osw access is serialized through one lock.

The osw library prints progress to ``stdout`` (e.g. "Connecting to ..."), but on
the stdio transport ``stdout`` is the JSON-RPC channel. The :func:`osw_guard`
context manager therefore redirects ``stdout`` to ``stderr`` for the duration of
each osw call (safe because the transport captured its own stream at startup and
the lock guarantees only one redirect at a time).
"""

from __future__ import annotations

import sys
import threading
from contextlib import contextmanager, redirect_stdout
from typing import Callable, Optional

from osw.auth import CredentialManager
from osw.express import OswExpress
from osw.service import config
from osw.service.ledger import Ledger

_LOCK = threading.RLock()
_osw: Optional[OswExpress] = None
_ledger: Optional[Ledger] = None


def _require_active_domain() -> str:
    """Return the active instance's domain, or raise a clear, actionable error."""
    domain = config.get_active_domain()
    if domain is None:
        available = ", ".join(config.available_iris()) or "(none)"
        raise RuntimeError(
            "No OSL instance selected. Call select_instance first; "
            f"available: {available}."
        )
    return domain


def get_osw() -> OswExpress:
    """Return the shared ``OswExpress``, connecting on first use.

    Credentials come from either of two sources, both already validated by
    :func:`osw.service.config.load`:

    * ``OSW_USERNAME`` / ``OSW_PASSWORD`` (or their ``OSL_*`` aliases), read
      by osw from the environment; or
    * a credential file (``settings.cred_filepath``), configured via
      ``OSW_MCP_CRED_FILEPATH`` / ``OSL_CRED_FILEPATH``, wrapped in a
      ``CredentialManager`` and passed to ``OswExpress`` explicitly.

    Connects to the active instance (see :mod:`osw.service.config`); raises if
    none is selected.
    """
    global _osw
    if _osw is None:
        settings = config.get_settings()
        domain = _require_active_domain()
        if settings.cred_filepath:
            cred_mngr = CredentialManager(cred_filepath=settings.cred_filepath)
            _osw = OswExpress(domain=domain, cred_mngr=cred_mngr)
        else:
            _osw = OswExpress(domain=domain)
    return _osw


def get_ledger() -> Ledger:
    """Return the shared provenance ledger, keyed on the active instance's domain."""
    global _ledger
    if _ledger is None:
        settings = config.get_settings()
        domain = _require_active_domain()
        _ledger = Ledger(domain=domain, state_dir=settings.state_dir)
    return _ledger


@contextmanager
def osw_guard():
    """Serialize osw access and keep osw's stdout off the protocol channel."""
    with _LOCK, redirect_stdout(sys.stderr):
        yield get_osw()


def run_guarded(fn: Callable[[OswExpress], dict]) -> dict:
    """Run ``fn(osw)`` under the guard, converting exceptions into error dicts.

    Keeps tool signatures clean (no ``osw`` parameter leaks into the MCP schema)
    and prevents stack traces from reaching the client; the model sees a
    structured ``{"error", "type"}`` instead.
    """
    try:
        with osw_guard() as osw:
            return fn(osw)
    except Exception as exc:
        print(f"[osw-mcp] tool error: {exc!r}", file=sys.stderr)
        return {"error": str(exc), "type": type(exc).__name__}


def reset() -> None:
    """Drop the shared connection and ledger so the next call rebuilds them.

    Called after switching the active instance (``select_instance``) so a
    stale connection or a ledger keyed on the previous domain is never reused.
    """
    global _osw, _ledger
    with _LOCK:
        if _osw is not None:
            try:
                with redirect_stdout(sys.stderr):
                    _osw.close_connection()
            except Exception as exc:
                print(f"[osw-mcp] error closing connection: {exc!r}", file=sys.stderr)
            _osw = None
        _ledger = None


def shutdown() -> None:
    """Close the connection on server exit."""
    reset()
