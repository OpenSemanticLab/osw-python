"""Unit tests for osw.mcp.registration (Operation -> mcp.tool() kwargs).

These are fully offline: no network, no live wiki.
"""

from __future__ import annotations

import pytest

pytest.importorskip("mcp", reason="requires the osw[mcp] extra")

from mcp.types import ToolAnnotations

from osw.mcp.registration import _annotations, _meta, tool_kwargs
from osw.service.config import Settings
from osw.service.registry import Operation


def _op(**kwargs) -> Operation:
    def fn(ctx) -> dict:
        """A test operation."""
        return {}

    fields = {"name": "an_op", "fn": fn, **kwargs}
    return Operation(**fields)


def _settings(**kwargs) -> Settings:
    fields = {"domain": "wiki.example.org", **kwargs}
    return Settings(**fields)


# -- _annotations -------------------------------------------------------------
def test_annotations_maps_every_hint_onto_its_named_field():
    op = _op(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )

    annotations = _annotations(op)

    assert isinstance(annotations, ToolAnnotations)
    # Assert on the real attributes (not a dict), so a misspelled field name
    # in _annotations -- silently absorbed by ToolAnnotations' extra-field
    # tolerance -- leaves these ``None`` and the test fails.
    assert annotations.read_only_hint is True
    assert annotations.destructive_hint is False
    assert annotations.idempotent_hint is True
    assert annotations.open_world_hint is False


def test_annotations_none_when_no_hint_is_set():
    op = _op()

    assert _annotations(op) is None


# -- _meta ----------------------------------------------------------------------
def test_meta_falls_back_to_settings_max_chars():
    op = _op()
    settings = _settings(max_chars=12_345)

    meta = _meta(op, settings)

    assert meta["anthropic/maxResultSizeChars"] == 12_345
    assert "anthropic/requiresUserInteraction" not in meta


def test_meta_honours_op_max_result_size_chars():
    op = _op(max_result_size_chars=999)
    settings = _settings(max_chars=12_345)

    meta = _meta(op, settings)

    assert meta["anthropic/maxResultSizeChars"] == 999


def test_meta_sets_requires_user_interaction_only_when_declared():
    plain = _meta(_op(), _settings())
    interactive = _meta(_op(requires_user_interaction=True), _settings())

    assert "anthropic/requiresUserInteraction" not in plain
    assert interactive["anthropic/requiresUserInteraction"] is True


def test_meta_extra_meta_merges_last():
    op = _op(extra_meta={"anthropic/maxResultSizeChars": 1, "custom": "x"})
    settings = _settings(max_chars=100)

    meta = _meta(op, settings)

    assert meta["anthropic/maxResultSizeChars"] == 1
    assert meta["custom"] == "x"


# -- tool_kwargs ------------------------------------------------------------------
def test_tool_kwargs_uses_name_and_docstring():
    op = _op()
    settings = _settings()

    kwargs = tool_kwargs(op, settings)

    assert kwargs["name"] == "an_op"
    assert kwargs["description"] == "A test operation."
    assert kwargs["annotations"] is None
    assert "anthropic/maxResultSizeChars" in kwargs["meta"]


# -- no instance-switching tools on the registered server ------------------------
def test_registered_server_exposes_no_instance_switching_tools(monkeypatch):
    from osw.mcp.tools import register_all
    from osw.service import config

    monkeypatch.setenv("OSW_DOMAIN", "wiki.example.org")
    monkeypatch.setenv("OSW_USERNAME", "u")
    monkeypatch.setenv("OSW_PASSWORD", "p")
    config.reset()

    class FakeMCP:
        def __init__(self):
            self.names = []

        def tool(self, *_args, **kwargs):
            def deco(fn):
                self.names.append(kwargs.get("name") or fn.__name__)
                return fn

            return deco

    fake = FakeMCP()
    try:
        register_all(fake, include_writes=True)
    finally:
        config.reset()

    # Assert something WAS registered first: the two absence checks below
    # would otherwise pass on an empty list.
    assert "get_entity" in fake.names
    assert "list_instances" not in fake.names
    assert "select_instance" not in fake.names
