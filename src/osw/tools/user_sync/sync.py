"""Orchestrator for the user-item sync tool.

Ties the sources, mapping, reconciliation, interactive and store steps into one
run: enumerate MediaWiki users, enrich ORCID users, reconcile against existing
items, preview and confirm, then store items, redirects and organizations and
verify.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from osw.core import OSW

from .build import apply_update, build_organization, build_user
from .config import SyncConfig
from .existing import adopt_existing_pages, load_existing_users
from .interactive import Prompter, Resolution, resolve_plan
from .mapping import ProposedOrganization, map_user
from .prune import clear_jsondata_keys
from .reconcile import REMOVE, existing_fields, reconcile
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
    pruned: List[str] = field(default_factory=list)
    redirects_created: List[str] = field(default_factory=list)
    organizations: List[str] = field(default_factory=list)
    missing_email: List[str] = field(default_factory=list)
    accepted: bool = False

    def summary(self) -> str:
        state = "applied" if self.accepted else "no changes written"
        return (
            f"{state}: created={len(self.created)} updated={len(self.updated)} "
            f"skipped={len(self.skipped)} pruned={len(self.pruned)} "
            f"failed={len(self.failed)} "
            f"redirects={len(self.redirects_created)} orgs={len(self.organizations)} "
            f"missing_email={len(self.missing_email)}"
        )


def _build_proposals(config: SyncConfig, osw: Any, session: Any):
    """Enumerate MediaWiki users, enrich ORCID users and map to proposals.

    Returns the proposed users, the organizations and the names of the blocked
    accounts that were skipped.
    """
    excluded = tuple(config.excluded_groups) if config.exclude_bot_group else ()
    reserved = RESERVED_USERNAMES if config.exclude_system_usernames else ()
    skipped_blocked: List[str] = []
    mw_users = enumerate_mw_users(
        osw.mw_site,
        excluded_groups=excluded,
        excluded_usernames=reserved,
        include_orcid=config.include_orcid,
        include_non_orcid=config.include_non_orcid,
        limit=config.limit,
        exclude_blocked=not config.include_blocked,
        skipped_blocked=skipped_blocked,
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
            mw_user,
            profile,
            include_websites=config.include_websites,
            link_organizations=config.link_organizations,
        )
        proposed_users.append(proposed)
        for org in orgs:
            org_map.setdefault(org.uuid, org)
    return proposed_users, org_map, skipped_blocked


def _record_partial(report: SyncReport, exc: Exception) -> List[str]:
    """Record each failed title of a partial store; return the stored titles."""
    for title, error in exc.failed.items():
        report.failed[f"store:{title}"] = str(error)
    return list(exc.stored)


def _store_organizations(osw: Any, org_map, report: SyncReport) -> None:
    if not org_map:
        return
    entities = [build_organization(org) for org in org_map.values()]
    try:
        osw.store_entity(
            OSW.StoreEntityParam(entities=entities, edit_comment="user-sync: orgs")
        )
        report.organizations = [org.full_page_title for org in org_map.values()]
    except OSW.StoreEntityPartialError as exc:
        report.organizations = _record_partial(report, exc)
    except Exception as exc:  # pragma: no cover - network failure path
        report.failed["organizations"] = str(exc)


def _store_users(
    osw: Any,
    resolution: Resolution,
    report: SyncReport,
    failed_orgs: FrozenSet[str] = frozenset(),
) -> None:
    """Store created and updated items; count a title only once it is stored.

    New links to an organization in ``failed_orgs`` are dropped, so no item
    points to an organization that was not stored. A link the existing item
    already has is kept. A re-run proposes the dropped links again.
    """
    entities = []
    pending: List[Tuple[str, str]] = []  # (action, title) per entity
    for resolved in resolution.resolved:
        proposed = resolved.change.proposed
        drop = set(proposed.organizations) & failed_orgs
        if drop and resolved.change.existing is not None:
            drop -= existing_fields(resolved.change.existing)["organizations"]
        if drop:
            proposed = replace(
                proposed,
                organizations=[o for o in proposed.organizations if o not in drop],
            )
        try:
            if resolved.action == "create":
                entities.append(build_user(proposed))
            elif resolved.action == "update":
                entities.append(
                    apply_update(
                        resolved.change.existing, proposed, resolved.apply_fields
                    )
                )
            else:
                report.skipped.append(proposed.full_page_title)
                continue
            pending.append((resolved.action, proposed.full_page_title))
        except Exception as exc:  # pragma: no cover - build failure path
            report.failed[f"build:{proposed.username}"] = str(exc)
    if not entities:
        return
    try:
        osw.store_entity(
            OSW.StoreEntityParam(
                entities=entities,
                overwrite=True,
                edit_comment="user-sync",
            )
        )
        stored = {title for _, title in pending}
    except OSW.StoreEntityPartialError as exc:
        stored = set(_record_partial(report, exc))
    except Exception as exc:  # pragma: no cover - network failure path
        report.failed["store"] = str(exc)
        stored = set()
    for action, title in pending:
        if title in stored:
            (report.created if action == "create" else report.updated).append(title)


# Names of reconciled fields mapped to their keys in the item's jsondata.
_JSONDATA_KEYS = {
    "websites": "website",
    "organizations": "organization",
    "employment_contract_status": "employment_contract_status",
}


def _prune_users(osw: Any, resolution: Resolution, report: SyncReport) -> None:
    """Clear removed fields of stored existing items (see clear_jsondata_keys)."""
    updated = set(report.updated)
    for resolved in resolution.resolved:
        if resolved.action != "update":
            continue
        if resolved.change.proposed.full_page_title not in updated:
            continue  # the update was not stored
        keys = [
            _JSONDATA_KEYS[d.name]
            for d in resolved.change.diffs
            if d.status == REMOVE
            and d.name in resolved.apply_fields
            and d.name in _JSONDATA_KEYS
        ]
        if not keys:
            continue
        title = resolved.change.proposed.full_page_title
        try:
            if clear_jsondata_keys(osw, title, keys):
                report.pruned.append(title)
        except Exception as exc:  # pragma: no cover - network failure path
            report.failed[f"prune:{title}"] = str(exc)


def _create_redirects(osw: Any, resolution: Resolution, report: SyncReport) -> None:
    # A redirect needs an existing target: an item stored in this run, or one
    # that existed before it (update or skip). A failed create gets none; a
    # re-run writes it once the item is stored.
    created = set(report.created)
    for resolved in resolution.resolved:
        proposed = resolved.change.proposed
        if resolved.action == "create" and proposed.full_page_title not in created:
            continue
        try:
            written = ensure_redirect(osw, proposed.username, proposed.full_page_title)
            if written:
                report.redirects_created.append(written)
        except Exception as exc:  # pragma: no cover - network failure path
            report.failed[f"redirect:{proposed.username}"] = str(exc)


def _warn_missing_email(prompter: Prompter, missing: List[str]) -> None:
    if missing:
        prompter.write(
            f"WARNING: {len(missing)} user(s) have no ORCID email: "
            + ", ".join(missing)
        )


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

    proposed_users, org_map, skipped_blocked = _build_proposals(config, osw, session)
    missing_email = [p.username for p in proposed_users if not p.emails]
    existing = load_existing_users(osw)
    adopt_existing_pages(osw, existing, proposed_users)
    plan = reconcile(
        proposed_users,
        existing,
        enabled_fields=frozenset(config.enabled_optional_fields()),
        prune=config.prune,
    )

    summary_lines = []
    if skipped_blocked:
        summary_lines.append(
            f"Skipped blocked accounts ({len(skipped_blocked)}): "
            + ", ".join(skipped_blocked)
        )
    if config.link_organizations and org_map:
        summary_lines.append(f"Organizations to ensure: {len(org_map)}")
    if config.create_redirects:
        summary_lines.append("Redirects: User:<username> -> item for created/updated")

    resolution = resolve_plan(
        plan,
        prompter,
        dry_run=config.dry_run,
        auto_apply=config.auto_apply,
        summary_lines=summary_lines,
    )

    report = SyncReport(accepted=resolution.accepted, missing_email=missing_email)
    if not resolution.accepted:
        _warn_missing_email(prompter, missing_email)
        return report

    failed_orgs: FrozenSet[str] = frozenset()
    if config.link_organizations:
        _store_organizations(osw, org_map, report)
        stored_orgs = set(report.organizations)
        failed_orgs = frozenset(
            o.full_page_title
            for o in org_map.values()
            if o.full_page_title not in stored_orgs
        )
    _store_users(osw, resolution, report, failed_orgs=failed_orgs)
    if config.prune and "store" not in report.failed:
        _prune_users(osw, resolution, report)
    if config.create_redirects:
        _create_redirects(osw, resolution, report)
    _verify(osw, report)
    _warn_missing_email(prompter, missing_email)
    return report
