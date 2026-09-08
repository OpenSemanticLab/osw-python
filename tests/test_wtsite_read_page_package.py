"""Unit tests for WtSite.read_page_package()'s JSON error handling.

Regression guard for #42: a malformed packages.json or slot file used to raise a
bare json.JSONDecodeError with no indication of which file was broken. Both
json.load() call sites must now name the offending file path.
"""

import json
import threading

import pytest

from osw.wtsite import WtSite


class _FakeSite:
    """Stands in for mwclient.Site, only used if a re-login is attempted."""

    host = "example.org"


def _make_fake_wtsite():
    """A WtSite that performs no network calls."""
    ws = WtSite.__new__(WtSite)
    ws._session_lock = threading.RLock()
    ws._site = _FakeSite()
    return ws


def _valid_packages_json():
    return {
        "packages": {
            "TestPkg": {
                "globalID": "org.test.TestPkg",
                "description": "test package",
                "version": "0.0.1",
                "baseURL": "https://example.org/",
                "pages": [
                    {
                        "name": "OSW123",
                        "namespace": "NS_ITEM",
                        "urlPath": "OSW123.wikitext",
                        "slots": {"jsondata": {"urlPath": "OSW123.slot_jsondata.json"}},
                    }
                ],
            }
        }
    }


def test_read_page_package_names_malformed_packages_json(tmp_path):
    packages_json_path = tmp_path / "packages.json"
    packages_json_path.write_text("{not valid json", encoding="utf-8")

    ws = _make_fake_wtsite()

    with pytest.raises(json.JSONDecodeError) as exc_info:
        ws.read_page_package(WtSite.ReadPagePackageParam(storage_path=tmp_path))

    assert str(packages_json_path) in str(exc_info.value)
    assert exc_info.value.__cause__ is not None


def test_read_page_package_names_malformed_slot_file(tmp_path):
    packages_json_path = tmp_path / "packages.json"
    packages_json_path.write_text(json.dumps(_valid_packages_json()), encoding="utf-8")
    slot_path = tmp_path / "OSW123.slot_jsondata.json"
    slot_path.write_text("{not valid json", encoding="utf-8")
    # The main slot content file also needs to exist for the dump to be read.
    (tmp_path / "OSW123.wikitext").write_text("some wikitext", encoding="utf-8")

    ws = _make_fake_wtsite()

    with pytest.raises(json.JSONDecodeError) as exc_info:
        ws.read_page_package(WtSite.ReadPagePackageParam(storage_path=tmp_path))

    assert str(slot_path) in str(exc_info.value)
    assert exc_info.value.__cause__ is not None
