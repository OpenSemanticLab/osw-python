"""Unit tests for package directory lookup in osw.controller.page_package.

Regression guard for #135: a package present in both the working dir and an
additional package dir must resolve to the working dir one, instead of raising
because the name was found more than once.
"""

import pytest

from osw.controller.page_package import find_first_package_dir, find_package_dir


@pytest.fixture
def two_dirs(tmp_path):
    """A working dir and an additional dir, both holding 'MyPackage'."""
    work_dir = tmp_path / "work"
    extra_dir = tmp_path / "extra"
    (work_dir / "MyPackage").mkdir(parents=True)
    (extra_dir / "MyPackage").mkdir(parents=True)
    return work_dir, extra_dir


def test_prefers_the_first_search_path(two_dirs):
    work_dir, extra_dir = two_dirs

    found = find_first_package_dir("MyPackage", [work_dir, extra_dir])

    assert found == work_dir / "MyPackage"


def test_search_order_decides(two_dirs):
    """The same two dirs in the other order resolve to the other package."""
    work_dir, extra_dir = two_dirs

    found = find_first_package_dir("MyPackage", [extra_dir, work_dir])

    assert found == extra_dir / "MyPackage"


def test_falls_through_to_a_later_path(two_dirs, tmp_path):
    _, extra_dir = two_dirs
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    found = find_first_package_dir("MyPackage", [empty_dir, extra_dir])

    assert found == extra_dir / "MyPackage"


def test_returns_none_when_nothing_matches(tmp_path):
    assert find_first_package_dir("MyPackage", [tmp_path]) is None


def test_returns_none_for_empty_search_paths():
    assert find_first_package_dir("MyPackage", None) is None


def test_find_package_dir_still_rejects_ambiguity(two_dirs):
    """The all-at-once helper keeps its previous behaviour."""
    work_dir, extra_dir = two_dirs

    with pytest.raises(ValueError):
        find_package_dir("MyPackage", [work_dir, extra_dir])


@pytest.fixture
def two_script_dirs(tmp_path):
    """A script dir and an additional dir, both holding 'MyPackage.py'."""
    script_dir = tmp_path / "scripts"
    extra_dir = tmp_path / "extra_scripts"
    script_dir.mkdir()
    extra_dir.mkdir()
    (script_dir / "MyPackage.py").write_text("# working copy")
    (extra_dir / "MyPackage.py").write_text("# dependency copy")
    return script_dir, extra_dir


def test_prefers_the_first_search_path_for_scripts(two_script_dirs):
    """The script lookup takes the same route, so files must resolve too."""
    script_dir, extra_dir = two_script_dirs

    found = find_first_package_dir("MyPackage.py", [script_dir, extra_dir])

    assert found == script_dir / "MyPackage.py"


def test_falls_through_to_a_later_script_dir(two_script_dirs, tmp_path):
    _, extra_dir = two_script_dirs
    empty_dir = tmp_path / "empty_scripts"
    empty_dir.mkdir()

    found = find_first_package_dir("MyPackage.py", [empty_dir, extra_dir])

    assert found == extra_dir / "MyPackage.py"
