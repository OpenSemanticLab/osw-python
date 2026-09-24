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
    # Websites and organizations are opt-in (off by default); email is standard.
    assert cfg.include_websites is False
    assert cfg.link_organizations is False
    assert cfg.prune is False  # removals are opt-in
    assert cfg.enabled_optional_fields() == set()
    assert cfg.exclude_system_usernames is True
    assert "bot" in cfg.excluded_groups
    assert "sysop" in cfg.excluded_groups
    assert USER_CATEGORY.startswith("Category:OSW")
    assert ORGANIZATION_CATEGORY.startswith("Category:OSW")


def test_include_system_flag():
    cfg = config_from_args(["--include-system"])
    assert cfg.exclude_system_usernames is False


def test_optional_field_flags():
    cfg = config_from_args(["--with-organizations", "--with-websites"])
    assert cfg.link_organizations is True
    assert cfg.include_websites is True
    assert cfg.enabled_optional_fields() == {"organizations", "websites"}


def test_with_extras_enables_all():
    cfg = config_from_args(["--with-extras"])
    assert cfg.enabled_optional_fields() == {"websites", "organizations"}


def test_prune_flag():
    assert config_from_args([]).prune is False
    assert config_from_args(["--prune"]).prune is True


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
    assert cfg.include_orcid is True


def test_account_scope_defaults_and_mw_only():
    cfg = SyncConfig()
    assert cfg.include_orcid is True
    assert cfg.include_non_orcid is True  # both are standard by default
    mw_only = config_from_args(["--mw-only"])
    assert mw_only.include_orcid is False
    assert mw_only.include_non_orcid is True


def test_report_summary():
    report = SyncReport(created=["Item:OSW1"], updated=["Item:OSW2"])
    assert "created=1" in report.summary()
    assert "updated=1" in report.summary()


def test_run_user_sync_requires_connection():
    import pytest

    with pytest.raises(ValueError, match="connection"):
        run_user_sync(SyncConfig())
