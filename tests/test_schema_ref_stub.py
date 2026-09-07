"""Unit tests for the missing-schema-page handling in osw.core.

Regression guard for #134: a $ref is rewritten to a local file name before the
page it names is fetched. When that page does not exist, no file was written
and no message reached the caller, so the failure surfaced much later as a
FileNotFoundError inside datamodel-code-generator.
"""

import json
import os

import pytest

from osw.core import collect_messages, get_model_dir_path, write_schema_stub


def test_stub_is_valid_empty_json(tmp_path):
    path = write_schema_stub(str(tmp_path), "undefined")

    with open(path, encoding="utf-8") as f:
        assert json.load(f) == {}


def test_stub_lands_where_the_rewritten_ref_points(tmp_path):
    """The $ref becomes '<name>.json' relative to the model dir."""
    path = write_schema_stub(str(tmp_path), "undefined")

    assert os.path.basename(path) == "undefined.json"
    assert os.path.dirname(path) == str(tmp_path)


def test_stub_creates_missing_directories(tmp_path):
    target = tmp_path / "nested" / "deeper"

    path = write_schema_stub(str(target), "undefined")

    assert os.path.isfile(path)


def test_stub_overwrites_an_existing_file(tmp_path):
    (tmp_path / "undefined.json").write_text('{"stale": true}', encoding="utf-8")

    path = write_schema_stub(str(tmp_path), "undefined")

    with open(path, encoding="utf-8") as f:
        assert json.load(f) == {}


def test_model_dir_is_next_to_core():
    model_dir = get_model_dir_path()

    assert os.path.basename(model_dir) == "model"
    assert os.path.isfile(os.path.join(model_dir, "entity.py"))


@pytest.mark.parametrize("source", [None, []])
def test_nothing_to_collect_leaves_the_target_alone(source):
    assert collect_messages(None, source) is None
    assert collect_messages(["a"], source) == ["a"]


def test_messages_are_collected_into_an_absent_target():
    assert collect_messages(None, ["a"]) == ["a"]


def test_messages_are_appended_without_duplicates():
    assert collect_messages(["a"], ["a", "b"]) == ["a", "b"]


def test_a_shared_list_is_not_iterated_while_appended_to():
    """_FetchSchemaParam.copy() is shallow, so both sides can be one list."""
    shared = ["a"]

    assert collect_messages(shared, shared) is shared
    assert shared == ["a"]


def test_collecting_does_not_mutate_the_source():
    source = ["b"]

    collect_messages(["a"], source)

    assert source == ["b"]
