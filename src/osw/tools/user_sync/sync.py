"""Orchestrator for the user-item sync tool.

Ties the sources, mapping, reconciliation, interactive and store steps into one
run: enumerate MediaWiki users, enrich ORCID users, reconcile against existing
items, preview and confirm, then store items, redirects and organizations and
verify.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from osw.core import OSW

from .build import apply_update, build_organization, build_user
from .config import SyncConfig
from .existing import load_existing_users
from .interactive import Prompter, Resolution, resolve_plan
from .mapping import ProposedOrganization, map_user
from .reconcile import reconcile
from .redirects import ensure_redirect
from .sources import (
    RESERVED_USERNAMES,
    OrcidRateLimitError,
    enumerate_mw_users,
    fetch_orcid_record,
)


@dataclass
class SyncReport:
    """Outcome of a sync run."""

    created: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    failed: Dict[str, str] = field(default_factory=dict)
    redirects_created: List[str] = field(default_factory=list)
    organizations: List[str] = field(default_factory=list)
    accepted: bool = False

    def summary(self) -> str:
        state = "applied" if self.accepted else "no changes written"
        return (
            f"{state}: created={len(self.created)} updated={len(self.updated)} "
            f"skipped={len(self.skipped)} failed={len(self.failed)} "
            f"redirects={len(self.redirects_created)} orgs={len(self.organizations)}"
        )


def _build_proposals(config: SyncConfig, osw: Any, session: Any):
    """Enumerate MediaWiki users, enrich ORCID users and map to proposals."""
    excluded = tuple(config.excluded_groups) if config.exclude_bot_group else ()
    reserved = RESERVED_USERNAMES if config.exclude_system_usernames else ()
    mw_users = enumerate_mw_users(
        osw.mw_site,
        excluded_groups=excluded,
        excluded_usernames=reserved,
        include_non_orcid=config.include_non_orcid,
        limit=config.limit,
    )
    cache: Dict[str, Any] = {}
    proposed_users = []
    org_map: Dict[Any, ProposedOrganization] = {}
    for mw_user in mw_users:
        profile = None
        if mw_user.is_orcid:
            try:
                profile = fetch_orcid_record(
                    mw_user.orcid_id,
                    session=session,
                    base=config.orcid_api_base,
                    cache=cache,
                )
            except OrcidRateLimitError:
                profile = None
        proposed, orgs = map_user(
            mw_user, profile, link_organizations=config.link_organizations
        )
        proposed_users.append(proposed)
        for org in orgs:
            org_map.setdefault(org.uuid, org)
    return proposed_users, org_map


def _store_organizations(osw: Any, org_map, report: SyncReport) -> None:
    if not org_map:
        return
    entities = [build_organization(org) for org in org_map.values()]
    try:
        osw.store_entity(
            OSW.StoreEntityParam(entities=entities, edit_comment="user-sync: orgs")
        )
        report.organizations = [org.full_page_title for org in org_map.values()]
    except Exception as exc:  # pragma: no cover - network failure path
        report.failed["organizations"] = str(exc)


def _store_users(osw: Any, resolution: Resolution, report: SyncReport) -> None:
    entities = []
    for resolved in resolution.resolved:
        proposed = resolved.change.proposed
        try:
            if resolved.action == "create":
                entities.append(build_user(proposed))
                report.created.append(proposed.full_page_title)
            elif resolved.action == "update":
                entities.append(
                    apply_update(
                        resolved.change.existing, proposed, resolved.apply_fields
                    )
                )
                report.updated.append(proposed.full_page_title)
            else:
                report.skipped.append(proposed.full_page_title)
        except Exception as exc:  # pragma: no cover - build failure path
            report.failed[f"build:{proposed.username}"] = str(exc)
    if entities:
        try:
            osw.store_entity(
                OSW.StoreEntityParam(
                    entities=entities, overwrite=True, edit_comment="user-sync"
                )
            )
        except Exception as exc:  # pragma: no cover - network failure path
            report.failed["store"] = str(exc)


def _create_redirects(osw: Any, resolution: Resolution, report: SyncReport) -> None:
    # Every in-scope user has an item (created or pre-existing), so ensure the
    # redirect for all of them; a re-run repairs any missing redirect.
    for resolved in resolution.resolved:
        proposed = resolved.change.proposed
        try:
            written = ensure_redirect(osw, proposed.username, proposed.full_page_title)
            if written:
                report.redirects_created.append(written)
        except Exception as exc:  # pragma: no cover - network failure path
            report.failed[f"redirect:{proposed.username}"] = str(exc)


def _verify(osw: Any, report: SyncReport) -> None:
    titles = report.created + report.updated
    if not titles:
        return
    try:
        loaded = osw.load_entity(titles)
        loaded_list = loaded if isinstance(loaded, list) else [loaded]
        found = {getattr(e, "username", None) for e in loaded_list}
        missing = [
            t
            for t, e in zip(titles, loaded_list)
            if getattr(e, "username", None) is None
        ]
        if missing or None in found:
            report.failed["verify"] = f"missing username on {missing}"
    except Exception as exc:  # pragma: no cover - network failure path
        report.failed["verify"] = str(exc)


def run_user_sync(
    config: SyncConfig,
    osw: Optional[OSW] = None,
    prompter: Optional[Prompter] = None,
    session: Any = None,
) -> SyncReport:
    """Create or update OSW User items from MediaWiki accounts and ORCID data."""
    if osw is None:
        raise ValueError("run_user_sync requires an authenticated OSW connection")
    prompter = prompter or Prompter()

    proposed_users, org_map = _build_proposals(config, osw, session)
    existing = load_existing_users(osw)
    plan = reconcile(proposed_users, existing)

    summary_lines = []
    if config.link_organizations and org_map:
        summary_lines.append(f"Organizations to ensure: {len(org_map)}")
    if config.create_redirects:
        summary_lines.append("Redirects: User:<username> -> item for created/updated")

    resolution = resolve_plan(
        plan,
        prompter,
        dry_run=config.dry_run,
        assume_yes=config.assume_yes,
        summary_lines=summary_lines,
    )

    report = SyncReport(accepted=resolution.accepted)
    if not resolution.accepted:
        return report

    if config.link_organizations:
        _store_organizations(osw, org_map, report)
    _store_users(osw, resolution, report)
    if config.create_redirects:
        _create_redirects(osw, resolution, report)
    _verify(osw, report)
    return report
