"""Unit tests for osw.cli.ops.install_skill (called directly).

tests/test_cli.py only exercises osw.cli.ops through the typer command tree
(runner.invoke), so this module calls the operation function directly instead.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

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
PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"
SKILL_VERSION_ENTRY = "src/osw/skills/osl-tasks/SKILL.md:version"


def _skill_frontmatter() -> dict:
    # The frontmatter is the YAML between the two leading '---' lines.
    _, frontmatter, _ = SKILL_MD_PATH.read_text(encoding="utf-8").split("---", 2)
    return yaml.safe_load(frontmatter)


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


def test_skill_version_matches_the_package_version():
    """The skill carries the osw version it ships with.

    python-semantic-release rewrites both in the release commit, so they can
    only differ when one of them was edited by hand.
    """
    skill_version = _skill_frontmatter()["metadata"]["version"]

    assert skill_version == _pyproject()["project"]["version"]


def test_skill_is_registered_for_the_release_version_bump():
    """Without this entry a release bumps pyproject.toml but not the skill.

    The version check above would only fail after that release, so this
    catches a removed entry at once.
    """
    variables = _pyproject()["tool"]["semantic_release"]["version_variables"]

    assert SKILL_VERSION_ENTRY in variables


def test_release_bump_rewrites_only_the_frontmatter_version(monkeypatch):
    """python-semantic-release rewrites every match of its pattern in the file.

    A body line such as 'version: 1.2.3' or 'osw version 1.2.3' would be
    rewritten on every release without any test failing, so run the release
    tool's own replacement and check that it changes exactly one line.
    """
    from semantic_release.version.declarations.pattern import (
        PatternVersionDeclaration,
    )
    from semantic_release.version.version import Version

    # The entry's path is relative to the repository root, where the release
    # tool runs.
    monkeypatch.chdir(PYPROJECT_PATH.parent)
    declaration = PatternVersionDeclaration.from_string_definition(
        SKILL_VERSION_ENTRY, "v{version}"
    )
    before = SKILL_MD_PATH.read_text(encoding="utf-8").splitlines()
    after = declaration.replace(Version.parse("99.99.99")).splitlines()

    assert len(after) == len(before)
    changed = [new for old, new in zip(before, after) if old != new]
    assert changed == ['  version: "99.99.99"']
