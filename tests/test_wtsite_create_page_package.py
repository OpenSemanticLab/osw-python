"""Unit tests for the PagePackageConfig.clear_content_dir purge flag, and for
the deterministic ordering of packages.json (#172).

Regression guard for #42: WtSite.create_page_package used to unconditionally
shutil.rmtree() the content directory. clear_content_dir defaults to True (no
behaviour change), but setting it to False must keep any existing content.

Regression guard for #172: WtSite.create_page_package wrote the "pages" array
of packages.json in an order that varied between runs whenever
config.include_files was True, causing spurious diffs.
"""

import json
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


def _make_file_page(ws, title):
    """A File: page whose dump() does not attempt a real file download."""
    page = WtPage(wtSite=ws, title=title, do_init=False)
    page.exists = True
    page.dump = lambda config, _title=title: package.PagePackagePage(
        name=_title.split(":")[-1], namespace="NS_FILE", slots={}
    )
    return page


def _find_order_sensitive_file_titles():
    """Two File: titles for which list(set([a, b])) != list(set([b, a])) under
    the current process's (randomized) string hash seed. Used to reproduce the
    hash-order dependent bug without relying on a specific PYTHONHASHSEED."""
    for i in range(1000):
        for j in range(i + 1, 1000):
            a, b = f"File:F{i}.png", f"File:F{j}.png"
            if list({a, b}) != list({b, a}):
                return a, b
    raise RuntimeError("could not find an order-sensitive pair of file titles")


def _make_bundle_and_config(tmp_path, subdir, titles, include_files=True):
    target = tmp_path / subdir
    target.mkdir(parents=True, exist_ok=True)
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
        config_path=target / "packages.json",
        content_path=target / "content",
        bundle=bundle,
        titles=titles,
        include_files=include_files,
    )


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


def test_create_page_package_per_page_file_order_is_deterministic(tmp_path):
    """Regression test for #172: the order in which a page's file references
    are discovered must not change where they end up in packages.json."""
    file_a, file_b = _find_order_sensitive_file_titles()
    extra_file = "File:Extra.png"

    def _run(subdir, reversed_refs):
        ws = _make_fake_wtsite()
        item1 = WtPage(wtSite=ws, title="Item:OSW1", do_init=False)
        item2 = WtPage(wtSite=ws, title="Item:OSW2", do_init=False)
        order = [file_b, file_a] if reversed_refs else [file_a, file_b]
        item1.find_file_page_refs_in_slots = lambda slots=None: list(order)
        item2.find_file_page_refs_in_slots = lambda slots=None: [extra_file]

        offline_pages = {
            "Item:OSW1": item1,
            "Item:OSW2": item2,
            file_a: _make_file_page(ws, file_a),
            file_b: _make_file_page(ws, file_b),
            extra_file: _make_file_page(ws, extra_file),
        }

        config = _make_bundle_and_config(
            tmp_path, subdir, titles=["Item:OSW1", "Item:OSW2"]
        )
        ws.create_page_package(
            WtSite.CreatePagePackageParam(
                config=config,
                offline_pages=offline_pages,
                debug=False,
            )
        )
        return json.loads(config.config_path.read_text(encoding="utf-8"))

    data_1 = _run("run1", reversed_refs=False)
    data_2 = _run("run2", reversed_refs=True)

    names_1 = [p["name"] for p in data_1["packages"]["TestPkg"]["pages"]]
    names_2 = [p["name"] for p in data_2["packages"]["TestPkg"]["pages"]]

    assert names_1 == names_2

    # Item:OSW1's own files sit between its dump and Item:OSW2's dump, and are
    # in sorted order.
    expected_file_names = sorted([file_a.split(":")[-1], file_b.split(":")[-1]])
    assert names_1[1:3] == expected_file_names


def test_create_page_package_shared_file_always_attaches_to_first_page(tmp_path):
    """Regression test for #172: a file referenced by several pages must
    always be attached to the same (first-configured) page, regardless of the
    order in which get_page's parallel fetch happens to complete."""
    shared_file = "File:Shared.png"

    def _run(subdir, reverse_fetch_order):
        ws = _make_fake_wtsite()
        item1 = WtPage(wtSite=ws, title="Item:OSW1", do_init=False)
        item2 = WtPage(wtSite=ws, title="Item:OSW2", do_init=False)
        item1.find_file_page_refs_in_slots = lambda slots=None: [shared_file]
        item2.find_file_page_refs_in_slots = lambda slots=None: [shared_file]

        pages_by_title = {
            "Item:OSW1": item1,
            "Item:OSW2": item2,
            shared_file: _make_file_page(ws, shared_file),
        }

        def fake_get_page(param):
            titles = list(param.titles)
            if reverse_fetch_order:
                titles = list(reversed(titles))
            selected = [pages_by_title[t] for t in titles]
            return WtSite.GetPageResult(pages=selected, errors=[])

        ws.get_page = fake_get_page

        config = _make_bundle_and_config(
            tmp_path, subdir, titles=["Item:OSW1", "Item:OSW2"]
        )
        ws.create_page_package(
            WtSite.CreatePagePackageParam(config=config, debug=False)
        )
        return json.loads(config.config_path.read_text(encoding="utf-8"))

    data_normal = _run("normal", reverse_fetch_order=False)
    data_reversed = _run("reversed", reverse_fetch_order=True)

    names_normal = [p["name"] for p in data_normal["packages"]["TestPkg"]["pages"]]
    names_reversed = [p["name"] for p in data_reversed["packages"]["TestPkg"]["pages"]]

    assert names_normal == names_reversed
    # Shared.png must be attached to Item:OSW1 (first in config.titles), even
    # when Item:OSW2 is fetched first.
    assert names_normal == ["OSW1", "Shared.png", "OSW2"]
