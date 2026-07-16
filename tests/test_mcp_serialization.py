"""Unit tests for osw.mcp.serialization."""

from pathlib import Path

from osw.mcp.serialization import cap_list, maybe_truncate, to_jsonable


def test_cap_list_under_limit():
    items, total, truncated = cap_list([1, 2, 3], 10)
    assert items == [1, 2, 3]
    assert total == 3
    assert truncated is False


def test_cap_list_over_limit():
    items, total, truncated = cap_list(list(range(10)), 3)
    assert items == [0, 1, 2]
    assert total == 10
    assert truncated is True


def test_maybe_truncate_short_string():
    value, truncated = maybe_truncate("hello", 100)
    assert value == "hello"
    assert truncated is False


def test_maybe_truncate_long_string():
    value, truncated = maybe_truncate("x" * 50, 10)
    assert value == "x" * 10
    assert truncated is True


def test_maybe_truncate_small_dict_roundtrips():
    value, truncated = maybe_truncate({"a": 1}, 100)
    assert value == {"a": 1}
    assert truncated is False


def test_maybe_truncate_large_dict_returns_truncated_json_string():
    big = {"items": list(range(1000))}
    value, truncated = maybe_truncate(big, 50)
    assert truncated is True
    assert isinstance(value, str)
    assert len(value) == 50


def test_maybe_truncate_none():
    value, truncated = maybe_truncate(None, 10)
    assert value is None
    assert truncated is False


def test_to_jsonable_falls_back_to_str():
    # Path and set are not natively JSON-serializable
    result = to_jsonable({"p": Path("/tmp/x"), "s": {1, 2}})
    assert isinstance(result["p"], str)
    assert isinstance(result["s"], str)
