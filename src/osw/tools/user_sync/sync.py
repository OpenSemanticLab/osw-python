"""Orchestrator for the user-item sync tool.

Later phases implement enumeration, ORCID enrichment, reconciliation, the
interactive layer and the store step. This module currently defines the report
type and the public entry point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from osw.core import OSW

from .config import SyncConfig


@dataclass
class SyncReport:
    """Outcome of a sync run."""

    created: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    failed: Dict[str, str] = field(default_factory=dict)
    redirects_created: List[str] = field(default_factory=list)
    organizations: List[str] = field(default_factory=list)

    def summary(self) -> str:
        """One-line human-readable summary of the run."""
        return (
            f"created={len(self.created)} updated={len(self.updated)} "
            f"skipped={len(self.skipped)} failed={len(self.failed)} "
            f"redirects={len(self.redirects_created)} orgs={len(self.organizations)}"
        )


def run_user_sync(config: SyncConfig, osw: Optional[OSW] = None) -> SyncReport:
    """Create or update OSW User items from MediaWiki accounts and ORCID data.

    Args:
        config: Runtime options for the run.
        osw: An authenticated OSW/OswExpress connection. Required for any wiki
            access; the example wrapper builds one from ``config``.
    """
    raise NotImplementedError("Implemented incrementally in phases 1 to 6.")
