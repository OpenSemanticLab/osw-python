"""Unit tests for register_schema()'s $ref post-processing (issue #101).

Regression guard: pydantic v1 only wraps a nested-model $ref in "allOf" when
the field carries extra metadata (e.g. Field(description=...)). A plain
nested-model field produces a bare {"$ref": ...} that the old code never
rewrote before deleting "definitions", leaving a dangling ref behind.

These run fully offline: WtPage.init and WtPage.edit are stubbed so no
network is required, following the pattern in test_store_entity_failure.py.
"""

import uuid

import pytest
from pydantic.v1 import Field

import osw.model.entity as model
from osw.core import OSW
from osw.wtsite import WtPage


class Inner(model.OswBaseModel):
    a: str = "x"


class OuterBare(model.OswBaseModel):
    """Nested field without Field(...) metadata: pydantic emits a bare $ref."""

    inner: Inner


class OuterAllOf(model.OswBaseModel):
    """Nested field with Field(description=...): pydantic wraps the $ref in allOf."""

    inner: Inner = Field(description="the inner thing")


class _FakeMwSite:
    host = "example.org"


class _FakeSite:
    mw_site = _FakeMwSite()


@pytest.fixture
def offline_osw(monkeypatch):
    # no network when a WtPage is constructed with do_init=True; mimic the
    # do_init=False branch of WtPage.__init__ which sets .exists
    monkeypatch.setattr(WtPage, "init", lambda self: setattr(self, "exists", False))
    captured_schemas = []

    def fake_edit(self, *args, **kwargs):
        captured_schemas.append(self._slots.get("jsonschema"))

    monkeypatch.setattr(WtPage, "edit", fake_edit)
    return OSW.construct(site=_FakeSite()), captured_schemas


def _register_and_get_schema(offline_osw, model_cls, name):
    osw, captured_schemas = offline_osw
    osw.register_schema(
        OSW.SchemaRegistration(
            model_cls=model_cls,
            schema_uuid=str(uuid.uuid4()),
            schema_name=name,
        )
    )
    return captured_schemas[-1]


def _has_dangling_ref(node):
    """Recursively look for a "dollarref" (register_schema's stand-in for
    "$ref") anywhere in the schema. Since register_schema only ever emits
    local (#/definitions/...) refs, any leftover one is dangling once
    "definitions" is removed.
    """
    if isinstance(node, dict):
        if "dollarref" in node:
            return True
        return any(_has_dangling_ref(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_dangling_ref(v) for v in node)
    return False


def test_bare_nested_ref_is_resolved_like_allof(offline_osw):
    """A nested field with no Field(...) metadata must not leave a dangling
    ref behind, and must be embedded the same way an allOf-wrapped ref is.
    """
    schema = _register_and_get_schema(offline_osw, OuterBare, "OuterBare")

    assert not _has_dangling_ref(schema)
    assert "definitions" not in schema
    assert schema["properties"]["inner"]["title"] == "Inner"
    assert schema["properties"]["inner"]["properties"]["a"]["type"] == "string"


def test_allof_wrapped_ref_is_still_resolved(offline_osw):
    """Existing behaviour for allOf-wrapped refs must be unchanged."""
    schema = _register_and_get_schema(offline_osw, OuterAllOf, "OuterAllOf")

    assert not _has_dangling_ref(schema)
    assert "definitions" not in schema
    assert schema["properties"]["inner"]["description"] == "the inner thing"
    assert schema["properties"]["inner"]["allOf"][0]["title"] == "Inner"
    assert (
        schema["properties"]["inner"]["allOf"][0]["properties"]["a"]["type"] == "string"
    )
