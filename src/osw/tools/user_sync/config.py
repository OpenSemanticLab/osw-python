"""Configuration for the user-item sync tool."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import List, Optional, Set

# Category page titles of the target item types (see opensemantic.base.v1).
USER_CATEGORY = "Category:OSWd9aa0bca9b0040d8af6f5c091bf9eec7"
ORGANIZATION_CATEGORY = "Category:OSW1969007d5acf40539642877659a02c23"

# Public ORCID API used to enrich ORCID users.
ORCID_API_BASE_DEFAULT = "https://pub.orcid.org/v3.0"

# MediaWiki groups whose members are treated as bot/system accounts and skipped.
# All are standard MediaWiki groups, so this is not a per-instance skip-list.
SYSTEM_GROUPS = ["bot", "sysop", "bureaucrat", "interface-admin"]

# User fields the script must never write and must remove from existing items
# (data protection).
PROTECTED_FIELDS = ("employment_contract_status",)


@dataclass
class SyncConfig:
    """Runtime options for a single sync run."""

    domain: Optional[str] = None
    cred_filepath: Optional[str] = None
    dry_run: bool = False
    auto_apply: bool = False
    limit: Optional[int] = None
    include_orcid: bool = True
    include_non_orcid: bool = True
    exclude_bot_group: bool = True
    exclude_system_usernames: bool = True
    create_redirects: bool = True
    # Optional enrichment beyond core identity, opt-in (off by default).
    # Email is not optional: it is always attempted, and missing emails are
    # reported as warnings rather than failing the run.
    include_websites: bool = False
    link_organizations: bool = False
    # Remove disabled optional fields and protected fields from existing items.
    prune: bool = False
    orcid_api_base: str = ORCID_API_BASE_DEFAULT
    excluded_groups: List[str] = field(default_factory=lambda: list(SYSTEM_GROUPS))

    def enabled_optional_fields(self) -> Set[str]:
        """Reconcile field names for the enabled optional data."""
        enabled: Set[str] = set()
        if self.include_websites:
            enabled.add("websites")
        if self.link_organizations:
            enabled.add("organizations")
        return enabled


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the argument parser used by the example wrapper."""
    parser = argparse.ArgumentParser(
        description="Create or update OSW User items from MediaWiki and ORCID.",
    )
    parser.add_argument("--domain", help="Target OSL domain, e.g. llm4eln.semos.dev.")
    parser.add_argument(
        "--cred-filepath",
        dest="cred_filepath",
        help="Path to accounts.pwd.yaml (defaults to the working directory).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the preview only; do not write anything.",
    )
    parser.add_argument(
        "--auto-apply",
        dest="auto_apply",
        action="store_true",
        help="Non-interactive: apply creates, gap-fills and removals; keep existing on conflicts.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process at most this many MediaWiki users (for testing).",
    )
    parser.add_argument(
        "--no-redirects",
        dest="create_redirects",
        action="store_false",
        help="Do not create User: redirect pages.",
    )
    parser.add_argument(
        "--with-websites",
        dest="include_websites",
        action="store_true",
        help="Also store ORCID researcher URLs on the user item (opt-in).",
    )
    parser.add_argument(
        "--with-organizations",
        dest="link_organizations",
        action="store_true",
        help="Also resolve ORCID affiliations to Organization items and link them.",
    )
    parser.add_argument(
        "--with-extras",
        dest="with_extras",
        action="store_true",
        help="Enable all optional data: websites and organizations.",
    )
    parser.add_argument(
        "--prune",
        dest="prune",
        action="store_true",
        help="Remove disabled optional fields and employment_contract_status from "
        "existing items (data cleanup). Off by default; a normal run only adds.",
    )
    account_scope = parser.add_mutually_exclusive_group()
    account_scope.add_argument(
        "--orcid-only",
        dest="include_non_orcid",
        action="store_false",
        help="Sync only accounts whose username is an ORCID iD.",
    )
    account_scope.add_argument(
        "--mw-only",
        dest="include_orcid",
        action="store_false",
        help="Sync only non-ORCID (MediaWiki-native) accounts.",
    )
    parser.add_argument(
        "--include-system",
        dest="exclude_system_usernames",
        action="store_false",
        help="Do not skip MediaWiki reserved system accounts (Maintenance script etc.).",
    )
    return parser


def config_from_args(argv: Optional[List[str]] = None) -> SyncConfig:
    """Parse command-line arguments into a SyncConfig."""
    args = build_arg_parser().parse_args(argv)
    return SyncConfig(
        domain=args.domain,
        cred_filepath=args.cred_filepath,
        dry_run=args.dry_run,
        auto_apply=args.auto_apply,
        limit=args.limit,
        include_orcid=args.include_orcid,
        include_non_orcid=args.include_non_orcid,
        exclude_system_usernames=args.exclude_system_usernames,
        create_redirects=args.create_redirects,
        include_websites=args.include_websites or args.with_extras,
        link_organizations=args.link_organizations or args.with_extras,
        prune=args.prune,
    )
