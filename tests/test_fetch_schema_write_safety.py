"""Unit tests for the sentinel-cleanup and syntax-validation guards in osw.core.

Regression guard for #125: datamodel-code-generator uses a bare
`UNDEFINED = object()` sentinel with `is` identity checks. oold's merge_deep
deep-copies schema dicts during allOf composition, which clones that sentinel
into a look-alike object, defeating the identity guard, so the generator
repr's it into source (see oold.generator.Generator.generate() for oold's own
workaround). _fetch_schema used to write that content straight to entity.py
and reload it, raising SyntaxError and poisoning every later `import
osw.core` in the process.

These tests exercise the extracted helpers directly, fully offline, and
never call the real (wiki- and network-backed) `_fetch_schema`.
"""

import ast

import pytest

from osw.core import ensure_valid_python_source, remove_unserializable_default_sentinels


def test_sentinel_default_is_rewritten_to_valid_python():
    """A repr'd sentinel object breaks ast.parse until the substitution runs."""
    bad = (
        "risk_assessment: RiskAssessmentProcess | None = Field("
        "default_factory=lambda :<object object at 0x000001A2B3C4D5E6>)\n"
    )
    with pytest.raises(SyntaxError):
        ast.parse(bad)

    fixed = remove_unserializable_default_sentinels(bad)

    assert "<object object at" not in fixed
    ast.parse(fixed)  # must not raise


def test_sentinel_wrapped_in_a_parse_obj_call_is_rewritten():
    """The shape actually reported in #125, where the sentinel sits inside a
    `parse_obj(...)` call and the field carries further keyword arguments.

    oold's own regex stops at the first `)` after the address, which is the
    one belonging to `parse_obj(`, and so leaves a dangling `)` behind.
    """
    bad = (
        "risk_assessment: RiskAssessmentProcess | None = Field("
        "default_factory=lambda :RiskAssessmentProcess.parse_obj("
        "<object object at 0x000001A2B3C4D5E6>), options={'a': 1})\n"
    )
    with pytest.raises(SyntaxError):
        ast.parse(bad)

    fixed = remove_unserializable_default_sentinels(bad)

    assert "<object object at" not in fixed
    assert "options={'a': 1}" in fixed  # trailing kwargs are preserved
    ast.parse(fixed)  # must not raise


def test_legitimate_default_factory_lambda_is_not_mangled():
    """A normal `default_factory=lambda: uuid4()` must survive untouched."""
    legit = "id: UUID = Field(default_factory=lambda: uuid4())\n"

    assert remove_unserializable_default_sentinels(legit) == legit


def test_ensure_valid_python_source_accepts_valid_source():
    ensure_valid_python_source("class Foo:\n    pass\n", "entity.py")  # no raise


def test_ensure_valid_python_source_raises_with_a_useful_message():
    bad = "class Foo(:\n    pass\n"

    with pytest.raises(SyntaxError) as exc_info:
        ensure_valid_python_source(bad, "entity.py")

    message = str(exc_info.value)
    assert "entity.py" in message
    assert "line 1" in message
    assert "class Foo(:" in message


def test_validation_failure_leaves_an_existing_target_untouched(tmp_path):
    """Mirrors the guarded write in _fetch_schema: validation runs before the
    file is ever opened for writing, so a bad generation never touches the
    previous, valid content sitting at the target path.
    """
    target = tmp_path / "entity.py"
    target.write_text("previous_valid_content = 1\n", encoding="utf-8")

    bad = "class Foo(:\n    pass\n"

    with pytest.raises(SyntaxError):
        ensure_valid_python_source(bad, str(target))
        target.write_text("corrupted", encoding="utf-8")  # never reached

    assert target.read_text(encoding="utf-8") == "previous_valid_content = 1\n"
