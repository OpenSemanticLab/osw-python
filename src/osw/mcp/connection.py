"""Shared, thread-safe connection to a live OSL instance.

A single process-wide ``OswExpress`` is built lazily on first use. Because
mwclient's session is not thread-safe and FastMCP runs synchronous tools in a
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

from osw.express import OswExpress

from . import config
from .ledger import Ledger

_LOCK = threading.RLock()
_osw: Optional[OswExpress] = None
_ledger: Optional[Ledger] = None


def get_osw() -> OswExpress:
    """Return the shared ``OswExpress``, connecting on first use.

    Credentials and domain are resolved by osw from the environment
    (``OSW_DOMAIN`` / ``OSW_USERNAME`` / ``OSW_PASSWORD``), which
    :func:`osw.mcp.config.load` has already validated as present.
    """
    global _osw
    if _osw is None:
        settings = config.get_settings()
        _osw = OswExpress(domain=settings.domain)
    return _osw


def get_ledger() -> Ledger:
    """Return the shared provenance ledger."""
    global _ledger
    if _ledger is None:
        settings = config.get_settings()
        _ledger = Ledger(domain=settings.domain, state_dir=settings.state_dir)
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
    """Drop the shared connection so the next call rebuilds it."""
    global _osw
    with _LOCK:
        if _osw is not None:
            try:
                with redirect_stdout(sys.stderr):
                    _osw.close_connection()
            except Exception as exc:
                print(f"[osw-mcp] error closing connection: {exc!r}", file=sys.stderr)
            _osw = None


def shutdown() -> None:
    """Close the connection on server exit."""
    reset()
