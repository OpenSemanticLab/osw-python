"""Unit tests for osw.cli.ops.install_skill (called directly).

tests/test_cli.py only exercises osw.cli.ops through the typer command tree
(runner.invoke), so this module calls the operation function directly instead.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from osw.cli import ops
from osw.service import errors, registry
from osw.service.config import Settings
from osw.service.context import Context, Policy

SKILL_MD_PATH = (
    Path(ops.__file__).resolve().parent.parent / "skills" / "osl-tasks" / "SKILL.md"
)


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
