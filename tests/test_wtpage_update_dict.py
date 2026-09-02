"""Unit tests for WtPage.update_dict and its merge helper.

Regression guard for #15: update_dict called wt.combine_into, a function that
has never existed in this repository, so every nested dict raised
AttributeError. It was also declared as an instance method but called as
WtPage.update_dict(a, b) in set_value, which raised TypeError before the
missing reference was ever reached.
"""

from typing import Any, Dict, Union

from osw.wtsite import WtPage, _combine_into


class OfflineWtPage(WtPage):
    """A WtPage that never touches a wiki, copied from tests/test_osl.py."""

    def __init__(self, wtSite: Any = None, title: str = None):
        self.wtSite = wtSite
        self.title = title
        self.exists = True
        self._original_content = ""
        self.changed: bool = False
        self._dict = []
        self._slots: Dict[str, Union[str, dict]] = {"main": ""}
        self._slots_changed: Dict[str, bool] = {"main": False}
        self._content_model: Dict[str, str] = {"main": "wikitext"}


def test_flat_values_are_replaced():
    combined = {"a": 1, "b": 2}

    _combine_into({"b": 3}, combined)

    assert combined == {"a": 1, "b": 3}


def test_nested_dicts_are_merged_not_replaced():
    """The point of the recursion: 'keep' has to survive the merge."""
    combined = {"outer": {"keep": 1, "change": 2}}

    _combine_into({"outer": {"change": 3, "add": 4}}, combined)

    assert combined == {"outer": {"keep": 1, "change": 3, "add": 4}}


def test_merging_recurses_to_any_depth():
    combined = {"a": {"b": {"c": {"keep": 1}}}}

    _combine_into({"a": {"b": {"c": {"add": 2}}}}, combined)

    assert combined == {"a": {"b": {"c": {"keep": 1, "add": 2}}}}


def test_a_dict_replaces_a_scalar():
    combined = {"a": "scalar"}

    _combine_into({"a": {"b": 1}}, combined)

    assert combined == {"a": {"b": 1}}


def test_a_scalar_replaces_a_dict():
    combined = {"a": {"b": 1}}

    _combine_into({"a": "scalar"}, combined)

    assert combined == {"a": "scalar"}


def test_a_new_nested_key_is_copied_not_aliased():
    """Otherwise editing the result would reach back into the update dict."""
    update = {"a": {"b": 1}}
    combined = {}

    _combine_into(update, combined)
    combined["a"]["b"] = 2

    assert update == {"a": {"b": 1}}


def test_keys_absent_from_update_are_untouched():
    combined = {"a": 1}

    _combine_into({}, combined)

    assert combined == {"a": 1}


def test_update_dict_merges_in_place_and_returns_none():
    combined = {"outer": {"keep": 1}}

    assert WtPage.update_dict(combined, {"outer": {"add": 2}}) is None
    assert combined == {"outer": {"keep": 1, "add": 2}}


def test_set_value_merges_into_the_existing_entry():
    """set_value(replace=False) is the only caller, and it was broken."""
    page = OfflineWtPage(title="Test")
    page._dict = [{"Template": {"keep": "yes", "change": "old"}}]

    page.set_value("$.*.Template", {"change": "new"})

    assert page._dict == [{"Template": {"keep": "yes", "change": "new"}}]


def test_set_value_with_replace_discards_the_existing_entry():
    page = OfflineWtPage(title="Test")
    page._dict = [{"Template": {"keep": "yes", "change": "old"}}]

    page.set_value("$.*.Template", {"change": "new"}, replace=True)

    assert page._dict == [{"Template": {"change": "new"}}]
