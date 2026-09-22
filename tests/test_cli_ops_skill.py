"""Unit tests for osw.cli.ops.install_skill (called directly).

tests/test_cli.py only exercises osw.cli.ops through the typer command tree
(runner.invoke), so this module calls the operation function directly instead.

The last two tests cover the release version stamping of the skill and of the
two other files that carry a copy of the osw version.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from osw.cli import ops
from osw.service import errors, registry
from osw.service.config import Settings
from osw.service.context import Context, Policy

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

SKILL_MD_PATH = (
    Path(ops.__file__).resolve().parent.parent / "skills" / "osl-tasks" / "SKILL.md"
)
REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
SKILL_VERSION_ENTRY = "src/osw/skills/osl-tasks/SKILL.md:version"
PLUGIN_VERSION_ENTRY = ".claude-plugin/plugin.json:version"
CITATION_VERSION_ENTRY = "CITATION.cff:version"

# There is deliberately no test that a stamped version equals
# project.version. A pull request is tested against its merge with main, and
# a release on main bumps pyproject.toml and every stamped file the branch
# does not touch. A branch that edits SKILL.md therefore keeps the older
# version in that one file, and such a test would fail for a branch that is
# correct. The two tests below cover the rot that matters: a missing
# registration, and a version line the release pattern no longer matches.


def _pyproject() -> dict:
    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))


def _ctx() -> Context:
    return Context(
        Settings(domain="wiki.example.org", username="u", password="p"),
        Policy(),
        osw=MagicMock(),
    )


def test_default_install_copies_skill_md(tmp_path):
    result = ops.install_skill(_ctx(), target_dir=str(tmp_path))

    installed = tmp_path / "osl-tasks" / "SKILL.md"
    assert installed.is_file()
    assert installed.read_text(encoding="utf-8") == SKILL_MD_PATH.read_text(
        encoding="utf-8"
    )
    assert "SKILL.md" in result["files"]


def test_unknown_name_raises_not_found(tmp_path):
    with pytest.raises(errors.NotFound) as exc_info:
        ops.install_skill(_ctx(), name="does-not-exist", target_dir=str(tmp_path))

    assert "osl-tasks" in str(exc_info.value)


def test_second_install_without_force_raises_op_error(tmp_path):
    ops.install_skill(_ctx(), target_dir=str(tmp_path))

    installed = tmp_path / "osl-tasks" / "SKILL.md"
    original_text = installed.read_text(encoding="utf-8")

    with pytest.raises(errors.OpError):
        ops.install_skill(_ctx(), target_dir=str(tmp_path))

    assert installed.read_text(encoding="utf-8") == original_text


def test_second_install_with_force_overwrites(tmp_path):
    ops.install_skill(_ctx(), target_dir=str(tmp_path))

    installed = tmp_path / "osl-tasks" / "SKILL.md"
    installed.write_text("clobbered", encoding="utf-8")

    ops.install_skill(_ctx(), target_dir=str(tmp_path), force=True)

    assert installed.read_text(encoding="utf-8") == SKILL_MD_PATH.read_text(
        encoding="utf-8"
    )


def test_install_skill_is_registered_on_the_cli_surface_only():
    assert registry.REGISTRY["install_skill"].surfaces == frozenset({"cli"})


def test_stamped_files_are_registered_for_the_release_version_bump():
    """Without these entries a release bumps pyproject.toml but not the file.

    The file would then keep the version it was committed with, release after
    release, and nothing else would report it.
    """
    variables = _pyproject()["tool"]["semantic_release"]["version_variables"]

    assert SKILL_VERSION_ENTRY in variables
    assert PLUGIN_VERSION_ENTRY in variables
    assert CITATION_VERSION_ENTRY in variables


@pytest.mark.parametrize(
    ("entry", "changed_line"),
    [
        (SKILL_VERSION_ENTRY, '  version: "99.99.99"'),
        (PLUGIN_VERSION_ENTRY, '  "version": "99.99.99",'),
        # CITATION.cff also holds 'cff-version', which the pattern's negative
        # lookbehind must keep out of the replacement.
        (CITATION_VERSION_ENTRY, "version: 99.99.99"),
    ],
    ids=["skill", "plugin", "citation"],
)
def test_release_bump_rewrites_only_the_version_line(entry, changed_line, monkeypatch):
    """python-semantic-release rewrites every match of its pattern in the file.

    A second line such as 'version: 1.2.3' or 'osw version 1.2.3' would be
    rewritten on every release without any test failing, so run the release
    tool's own replacement and check that it changes exactly one line.
    """
    from semantic_release.version.declarations.pattern import (
        PatternVersionDeclaration,
    )
    from semantic_release.version.version import Version

    # The entry's path is relative to the repository root, where the release
    # tool runs.
    monkeypatch.chdir(REPO_ROOT)
    declaration = PatternVersionDeclaration.from_string_definition(entry, "v{version}")
    # Read the file the way the release tool does. It uses the locale
    #  encoding, which on Windows decodes a UTF-8 umlaut as two characters,
    #  and a comparison against our own UTF-8 read would report that line as
    #  changed.
    before = declaration.content.splitlines()
    after = declaration.replace(Version.parse("99.99.99")).splitlines()

    assert len(after) == len(before)
    changed = [new for old, new in zip(before, after) if old != new]
    assert changed == [changed_line]
