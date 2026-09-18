"""Unit tests for WtSite._replace_jsonld_context_mapping().

Regression guard for #177: the method rewrote the context object it was given
in place, so a caller that still needed its own dictionary got it modified.
It must now rewrite a copy and leave the argument untouched. An argument of an
unhandled type must be returned unchanged instead of an implicit None.
"""

import threading

from osw.wtsite import WtSite


class _FakeSite:
    """Stands in for mwclient.Site. Only the host is read."""

    host = "example.org"


def _make_fake_wtsite():
    """A WtSite that performs no network calls."""
    ws = WtSite.__new__(WtSite)
    ws._session_lock = threading.RLock()
    ws._site = _FakeSite()
    return ws


def _params():
    return WtSite.JsonLdContextLoaderParams(prefer_external_vocal=False)


def test_dict_argument_is_not_modified():
    ws = _make_fake_wtsite()
    given = {
        "label": {"@id": "skos:prefLabel"},
        "label*": {"@id": "Property:HasLabel"},
        "wiki": "https://original.example/id/",
    }

    result = ws._replace_jsonld_context_mapping(given, _params())

    assert result is not given
    assert given == {
        "label": {"@id": "skos:prefLabel"},
        "label*": {"@id": "Property:HasLabel"},
        "wiki": "https://original.example/id/",
    }


def test_dict_argument_is_still_rewritten_in_the_result():
    ws = _make_fake_wtsite()
    given = {
        "label": {"@id": "skos:prefLabel"},
        "label*": {"@id": "Property:HasLabel"},
        "wiki": "https://original.example/id/",
    }

    result = ws._replace_jsonld_context_mapping(given, _params())

    assert result["label"] == {"@id": "Property:HasLabel"}
    assert result["wiki"] == "https://example.org/id/"


def test_string_mapping_is_rewritten_without_touching_the_argument():
    ws = _make_fake_wtsite()
    given = {"label": "skos:prefLabel", "label*": "Property:HasLabel"}

    result = ws._replace_jsonld_context_mapping(given, _params())

    assert result["label"] == "Property:HasLabel"
    assert given["label"] == "skos:prefLabel"


def test_nested_values_are_not_shared_with_the_argument():
    ws = _make_fake_wtsite()
    nested = {"@id": "skos:prefLabel", "@type": "@id"}
    given = {"label": nested}

    result = ws._replace_jsonld_context_mapping(given, _params())

    assert result["label"] is not nested
    result["label"]["@id"] = "changed"
    assert nested["@id"] == "skos:prefLabel"


def test_scoped_context_is_not_modified():
    ws = _make_fake_wtsite()
    scoped = {
        "label": {"@id": "skos:prefLabel"},
        "label*": {"@id": "Property:HasLabel"},
    }
    given = {"statements": {"@context": scoped}}

    result = ws._replace_jsonld_context_mapping(given, _params())

    assert result["statements"]["label"] == {"@id": "Property:HasLabel"}
    assert scoped["label"] == {"@id": "skos:prefLabel"}


def test_list_elements_are_not_modified():
    ws = _make_fake_wtsite()
    element = {
        "label": {"@id": "skos:prefLabel"},
        "label*": {"@id": "Property:HasLabel"},
    }
    given = ["/wiki/Category:Entity?action=raw&slot=jsonschema", element]

    result = ws._replace_jsonld_context_mapping(given, _params())

    assert result is not given
    assert result[0] == "/wiki/Category:Entity?action=raw&slot=jsonschema"
    assert result[1] is not element
    assert result[1]["label"] == {"@id": "Property:HasLabel"}
    assert element["label"] == {"@id": "skos:prefLabel"}


def test_list_value_inside_a_dict_is_not_modified():
    ws = _make_fake_wtsite()
    element = {
        "label": {"@id": "skos:prefLabel"},
        "label*": {"@id": "Property:HasLabel"},
    }
    given = {"statements": [element]}

    result = ws._replace_jsonld_context_mapping(given, _params())

    assert result["statements"][0]["label"] == {"@id": "Property:HasLabel"}
    assert element["label"] == {"@id": "skos:prefLabel"}


def test_string_argument_is_returned_unchanged():
    ws = _make_fake_wtsite()
    assert ws._replace_jsonld_context_mapping("schema:name", _params()) == "schema:name"


def test_unhandled_type_is_returned_unchanged():
    ws = _make_fake_wtsite()
    assert ws._replace_jsonld_context_mapping(42, _params()) == 42
    assert ws._replace_jsonld_context_mapping(None, _params()) is None
