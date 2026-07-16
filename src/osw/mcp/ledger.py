"""Provenance ledger for the osw-mcp server.

The server records every page it *creates or modifies* through its own mutating
tools. Deleting a tracked page is allowed automatically; deleting a page the
server never touched requires an explicit ``confirm_external_delete`` override.

The ledger is a small JSON file (never credentials) stored in an OS-appropriate
state directory, namespaced by domain so multiple instances do not collide.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

LEDGER_VERSION = 1


def _default_state_dir() -> Path:
    """Return an OS-appropriate per-user state directory (no extra dependency)."""
    if sys.platform.startswith("win"):
        base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.getenv("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "osw-mcp"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_domain(domain: str) -> str:
    """Turn a domain into a filesystem-safe filename fragment."""
    return "".join(c if c.isalnum() or c in "-._" else "_" for c in domain)


class Ledger:
    """A JSON-backed record of pages created/modified by this server."""

    def __init__(self, domain: str, state_dir: Optional[str] = None):
        self.domain = domain
        base = Path(state_dir) if state_dir else _default_state_dir()
        self.path = base / f"ledger-{_safe_domain(domain)}.json"

    # -- persistence -------------------------------------------------------
    def _load(self) -> dict:
        if not self.path.is_file():
            return {"version": LEDGER_VERSION, "domain": self.domain, "entries": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            # A corrupt ledger must not take the server down; start fresh but
            # warn so the operator can investigate.
            print(
                f"[osw-mcp] ledger at {self.path} unreadable ({exc}); "
                "starting a new one.",
                file=sys.stderr,
            )
            return {"version": LEDGER_VERSION, "domain": self.domain, "entries": {}}
        data.setdefault("entries", {})
        return data

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)  # atomic on POSIX and Windows

    # -- public API --------------------------------------------------------
    def record(
        self,
        title: str,
        *,
        op: str,
        tool: str,
        uuid: Optional[str] = None,
        namespace: Optional[str] = None,
        change_id: Optional[str] = None,
        slots: Optional[List[str]] = None,
    ) -> None:
        """Upsert a create/update record for ``title`` (idempotent, merging)."""
        data = self._load()
        entry = data["entries"].get(title)
        now = _now()
        if entry is None:
            entry = {
                "title": title,
                "uuid": uuid,
                "namespace": namespace,
                "first_created_at": now,
                "last_modified_at": now,
                "change_ids": [],
                "ops": [],
                "tools": [],
                "slots_written": [],
                "deleted_at": None,
            }
            data["entries"][title] = entry
        entry["last_modified_at"] = now
        entry["deleted_at"] = None  # a re-created/edited page is tracked again
        if uuid and not entry.get("uuid"):
            entry["uuid"] = uuid
        if namespace and not entry.get("namespace"):
            entry["namespace"] = namespace
        if change_id and change_id not in entry["change_ids"]:
            entry["change_ids"].append(change_id)
        entry["ops"].append(op)
        if tool not in entry["tools"]:
            entry["tools"].append(tool)
        for slot in slots or []:
            if slot not in entry["slots_written"]:
                entry["slots_written"].append(slot)
        self._save(data)

    def is_tracked(self, title: str) -> bool:
        """True if ``title`` was created/modified by this server and not deleted."""
        entry = self._load()["entries"].get(title)
        return entry is not None and entry.get("deleted_at") is None

    def mark_deleted(self, title: str) -> None:
        """Mark ``title`` as deleted (kept for audit, not purged)."""
        data = self._load()
        entry = data["entries"].get(title)
        if entry is not None:
            entry["deleted_at"] = _now()
            self._save(data)

    def entry_count(self) -> int:
        """Number of currently-tracked (non-deleted) entries."""
        return sum(
            1 for e in self._load()["entries"].values() if e.get("deleted_at") is None
        )
