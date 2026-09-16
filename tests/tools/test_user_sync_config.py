"""Unit tests for the user-sync configuration and public surface."""

from osw.tools.user_sync import (
    ORGANIZATION_CATEGORY,
    USER_CATEGORY,
    SyncConfig,
    SyncReport,
    config_from_args,
    run_user_sync,
)


def test_defaults():
    cfg = SyncConfig()
    assert cfg.include_non_orcid is True
    assert cfg.create_redirects is True
    assert cfg.link_organizations is True
    assert cfg.excluded_groups == ["bot"]
    assert USER_CATEGORY.startswith("Category:OSW")
    assert ORGANIZATION_CATEGORY.startswith("Category:OSW")


def test_config_from_args_parses_flags():
    cfg = config_from_args([
        "--domain",
        "llm4eln.semos.dev",
        "--dry-run",
        "--limit",
        "5",
        "--orcid-only",
    ])
    assert cfg.domain == "llm4eln.semos.dev"
    assert cfg.dry_run is True
    assert cfg.limit == 5
    assert cfg.include_non_orcid is False


def test_report_summary():
    report = SyncReport(created=["Item:OSW1"], updated=["Item:OSW2"])
    assert "created=1" in report.summary()
    assert "updated=1" in report.summary()


def test_run_user_sync_requires_connection():
    import pytest

    with pytest.raises(ValueError, match="connection"):
        run_user_sync(SyncConfig())
