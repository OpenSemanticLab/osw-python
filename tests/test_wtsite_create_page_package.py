"""Unit tests for the PagePackageConfig.clear_content_dir purge flag.

Regression guard for #42: WtSite.create_page_package used to unconditionally
shutil.rmtree() the content directory. clear_content_dir defaults to True (no
behaviour change), but setting it to False must keep any existing content.
"""

import threading

import pytest

import osw.model.page_package as package
from osw.wtsite import WtPage, WtSite


class _FakeSite:
    """Stands in for mwclient.Site, only used if a re-login is attempted."""

    host = "example.org"


def _make_fake_wtsite():
    """A WtSite that performs no network calls."""
    ws = WtSite.__new__(WtSite)
    ws._session_lock = threading.RLock()
    ws._site = _FakeSite()
    return ws


def _make_config(tmp_path, clear_content_dir):
    bundle = package.PagePackageBundle(
        packages={
            "TestPkg": package.PagePackage(
                globalID="org.test.TestPkg",
                description="test package",
                version="0.0.1",
                baseURL="https://example.org/",
            )
        }
    )
    return package.PagePackageConfig(
        name="TestPkg",
        config_path=tmp_path / "packages.json",
        content_path=tmp_path / "content",
        bundle=bundle,
        titles=["Item:OSW123"],
        include_files=False,
        clear_content_dir=clear_content_dir,
    )


def test_clear_content_dir_defaults_to_true(tmp_path):
    bundle = package.PagePackageBundle(packages={})
    config = package.PagePackageConfig(
        name="TestPkg",
        config_path=tmp_path / "packages.json",
        titles=["Item:OSW123"],
        bundle=bundle,
    )
    assert config.clear_content_dir is True


@pytest.mark.parametrize("clear_content_dir", [True, False])
def test_create_page_package_honours_clear_content_dir(tmp_path, clear_content_dir):
    ws = _make_fake_wtsite()
    page = WtPage(wtSite=ws, title="Item:OSW123", do_init=False)

    content_path = tmp_path / "content"
    content_path.mkdir()
    marker = content_path / "marker.txt"
    marker.write_text("pre-existing content", encoding="utf-8")

    config = _make_config(tmp_path, clear_content_dir=clear_content_dir)

    ws.create_page_package(
        WtSite.CreatePagePackageParam(
            config=config,
            offline_pages={"Item:OSW123": page},
            debug=False,
        )
    )

    if clear_content_dir:
        assert not marker.exists()
    else:
        assert marker.exists()
