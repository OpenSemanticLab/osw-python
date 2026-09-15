"""Configuration for the user-item sync tool."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import List, Optional

# Category page titles of the target item types (see opensemantic.base.v1).
USER_CATEGORY = "Category:OSWd9aa0bca9b0040d8af6f5c091bf9eec7"
ORGANIZATION_CATEGORY = "Category:OSW1969007d5acf40539642877659a02c23"

# Public ORCID API used to enrich ORCID users.
ORCID_API_BASE_DEFAULT = "https://pub.orcid.org/v3.0"

# MediaWiki group whose members are excluded from the sync (bots).
BOT_GROUP = "bot"


@dataclass
class SyncConfig:
    """Runtime options for a single sync run."""

    domain: Optional[str] = None
    cred_filepath: Optional[str] = None
    dry_run: bool = False
    assume_yes: bool = False
    limit: Optional[int] = None
    include_non_orcid: bool = True
    exclude_bot_group: bool = True
    create_redirects: bool = True
    link_organizations: bool = True
    orcid_api_base: str = ORCID_API_BASE_DEFAULT
    excluded_groups: List[str] = field(default_factory=lambda: [BOT_GROUP])


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
        "--yes",
        dest="assume_yes",
        action="store_true",
        help="Non-interactive: apply new items and gap-fills, keep existing on conflicts.",
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
        "--no-organizations",
        dest="link_organizations",
        action="store_false",
        help="Do not resolve or link ORCID affiliations to Organization items.",
    )
    parser.add_argument(
        "--include-non-orcid",
        dest="include_non_orcid",
        action="store_true",
        default=True,
        help="Also sync non-bot accounts without an ORCID username (default).",
    )
    parser.add_argument(
        "--orcid-only",
        dest="include_non_orcid",
        action="store_false",
        help="Sync only accounts whose username is an ORCID iD.",
    )
    return parser


def config_from_args(argv: Optional[List[str]] = None) -> SyncConfig:
    """Parse command-line arguments into a SyncConfig."""
    args = build_arg_parser().parse_args(argv)
    return SyncConfig(
        domain=args.domain,
        cred_filepath=args.cred_filepath,
        dry_run=args.dry_run,
        assume_yes=args.assume_yes,
        limit=args.limit,
        include_non_orcid=args.include_non_orcid,
        create_redirects=args.create_redirects,
        link_organizations=args.link_organizations,
    )
