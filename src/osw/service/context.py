"""Per-instance execution context shared by every osw.service adapter.

Replaces the module-level globals in :mod:`osw.mcp.connection` (``_osw``,
``_ledger``, ``_LOCK``) with an object, so a single process can hold more than
one connected instance and tests can inject a fake ``osw``/``ledger`` instead
of monkeypatching a module.

The osw library prints progress to ``stdout`` (e.g. "Connecting to ..."). On
the MCP stdio transport ``stdout`` is the JSON-RPC channel, so
:meth:`Context.guard` redirects it to ``stderr`` for the duration of each osw
call -- but only when ``policy.capture_stdout`` is set. A plain CLI run wants
that progress output visible, so its policy leaves stdout alone.
"""

from __future__ import annotations

import sys
import threading
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass
from typing import Optional

from osw.auth import CredentialManager
from osw.express import OswExpress
from osw.service import config, errors
from osw.service.config import Settings
from osw.service.ledger import Ledger
from osw.wtsite import WtSite


@dataclass(frozen=True)
class Policy:
    """How an adapter wants operations to behave."""

    capture_stdout: bool = False  # stdout is the JSON-RPC channel (MCP) or --json
    errors_as_dicts: bool = False  # a model needs a result; a shell needs an exit code
    allow_writes: bool = True
    allow_interactive: bool = False  # a prompt would eat the JSON-RPC stream


class Context:
    """Everything a bound operation needs to run against one OSL instance.

    ``osw`` and ``ledger`` are built lazily on first access; tests may instead
    pre-set them (via the constructor or by assigning the attribute directly)
    to inject a fake without monkeypatching a module.
    """

    def __init__(
        self,
        settings: Settings,
        policy: Optional[Policy] = None,
        *,
        osw: Optional[OswExpress] = None,
        ledger: Optional[Ledger] = None,
    ) -> None:
        self.settings = settings
        self.policy = policy if policy is not None else Policy()
        self._osw = osw
        self._ledger = ledger
        self._lock = threading.RLock()

    def _require_active_domain(self) -> str:
        """Return the active instance's domain, or raise a clear, actionable error."""
        domain = config.get_active_domain()
        if domain is None:
            available = ", ".join(config.available_iris()) or "(none)"
            raise errors.NotConfigured(
                "No OSL instance selected. Call select_instance first; "
                f"available: {available}."
            )
        return domain

    @property
    def osw(self) -> OswExpress:
        """The shared ``OswExpress``, connecting on first use.

        Credentials come from either of two sources, both already validated
        by :func:`osw.service.config.load`:

        * ``OSW_USERNAME`` / ``OSW_PASSWORD`` (or their ``OSL_*`` aliases),
          read by osw from the environment; or
        * a credential file (``settings.cred_filepath``), wrapped in a
          ``CredentialManager`` and passed to ``OswExpress`` explicitly.
        """
        if self._osw is None:
            domain = self._require_active_domain()
            if self.settings.cred_filepath:
                cred_mngr = CredentialManager(cred_filepath=self.settings.cred_filepath)
                self._osw = OswExpress(domain=domain, cred_mngr=cred_mngr)
            else:
                self._osw = OswExpress(domain=domain)
        return self._osw

    @osw.setter
    def osw(self, value: Optional[OswExpress]) -> None:
        self._osw = value

    @property
    def ledger(self) -> Ledger:
        """The shared provenance ledger, keyed on the active instance's domain."""
        if self._ledger is None:
            domain = self._require_active_domain()
            self._ledger = Ledger(domain=domain, state_dir=self.settings.state_dir)
        return self._ledger

    @ledger.setter
    def ledger(self, value: Optional[Ledger]) -> None:
        self._ledger = value

    @contextmanager
    def guard(self):
        """Serialize access to this context's instance for the call's duration.

        Redirects ``stdout`` to ``stderr`` only when ``policy.capture_stdout``
        is set (a plain CLI run wants osw's progress output visible).
        """
        with self._lock:
            if self.policy.capture_stdout:
                with redirect_stdout(sys.stderr):
                    yield
            else:
                yield

    def limit(self, n: Optional[int]) -> int:
        """Return ``n`` if given and truthy, else the configured default."""
        return n or self.settings.max_results

    def page(self, title: str):
        """Return the page for ``title``.

        Raises :class:`osw.service.errors.NotFound` if it does not exist.
        """
        page = self.osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
        if not page.exists:
            raise errors.NotFound(f"Page '{title}' does not exist.")
        return page

    def require_write(self, op_name: str) -> None:
        """Raise if this context's policy disallows writes."""
        if not self.policy.allow_writes:
            raise errors.ReadOnly(
                f"Operation '{op_name}' is not permitted: writes are disabled "
                "(set OSW_READ_ONLY=false to allow)."
            )

    def reset(self) -> None:
        """Drop the held connection and ledger so the next access rebuilds them."""
        with self._lock:
            if self._osw is not None:
                try:
                    with redirect_stdout(sys.stderr):
                        self._osw.close_connection()
                except Exception as exc:
                    print(f"[osw] error closing connection: {exc!r}", file=sys.stderr)
                self._osw = None
            self._ledger = None

    def close(self) -> None:
        """Close the connection (e.g. on adapter shutdown)."""
        self.reset()
