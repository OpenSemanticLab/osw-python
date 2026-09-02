import warnings
from unittest.mock import MagicMock

import pytest

import osw.wiki_tools as wt


def test_create_flat_content_structure_from_wikitext():
    wikitext = "{{Template|param=value}}"
    expected = [{"Template": {"param": ["value"]}}]
    result = wt.create_flat_content_structure_from_wikitext(wikitext)
    assert result == expected


def _ask_result(*titles):
    """Build a minimal SMW ``ask`` API result dict for the given page titles."""
    return {
        "query": {
            "results": {
                title: {
                    "fulltext": title,
                    "fullurl": f"https://example.org/wiki/{title}",
                    "namespace": 0,
                    "exists": "1",
                    "displaytitle": "",
                    "printouts": {"SomeProperty": [f"{title}-value"]},
                }
                for title in titles
            }
        }
    }


def _ask_result_empty():
    """Build the SMW ``ask`` API result dict for a zero-result query, mirroring
    SMW's behaviour of serialising an empty result set as a JSON array."""
    return {"query": {"results": []}}


def test_semantic_search_return_json_single_query_returns_list_with_dict():
    result = _ask_result("Item:OSW1")
    site = MagicMock()
    site.api.return_value = result

    out = wt.semantic_search(
        site, wt.SearchParam(query="[[HasType::Category:Item]]", return_json=True)
    )

    # A single query still returns a list (of one raw result dict), not a bare dict
    # and not a flattened list of keys
    assert isinstance(out, list)
    assert out == [result]
    # printouts must be preserved intact
    assert out[0]["query"]["results"]["Item:OSW1"]["printouts"] == {
        "SomeProperty": ["Item:OSW1-value"]
    }


def test_semantic_search_return_json_list_returns_list_of_dicts():
    result_a = _ask_result("Item:OSW1")
    result_b = _ask_result("Item:OSW2")
    site = MagicMock()
    site.api.side_effect = [result_a, result_b]

    out = wt.semantic_search(
        site,
        wt.SearchParam(
            query=["[[HasType::Category:Item]]", "[[HasType::Category:Person]]"],
            return_json=True,
        ),
    )

    # A list of queries must return a list of result dicts, one per query
    assert isinstance(out, list)
    assert out == [result_a, result_b]


def test_semantic_search_returns_flat_list_of_titles():
    result = _ask_result("Item:OSW1", "Item:OSW2")
    site = MagicMock()
    site.api.return_value = result

    out = wt.semantic_search(site, "[[HasType::Category:Item]]")

    # return_json=False (the default) still yields a flat list of page titles
    assert out == ["Item:OSW1", "Item:OSW2"]


def test_semantic_search_zero_results_returns_empty_list():
    site = MagicMock()
    site.api.return_value = _ask_result_empty()

    out = wt.semantic_search(site, "[[HasType::Category:Nonexistent]]")

    assert out == []


def test_semantic_search_zero_results_return_json_returns_list_with_dict():
    result = _ask_result_empty()
    site = MagicMock()
    site.api.return_value = result

    out = wt.semantic_search(
        site,
        wt.SearchParam(query="[[HasType::Category:Nonexistent]]", return_json=True),
    )

    assert out == [result]


def test_semantic_search_batch_with_one_zero_result_query():
    result_a = _ask_result("Item:OSW1")
    result_b = _ask_result_empty()
    result_c = _ask_result("Item:OSW3")
    site = MagicMock()
    site.api.side_effect = [result_a, result_b, result_c]

    out = wt.semantic_search(
        site,
        wt.SearchParam(
            query=[
                "[[HasType::Category:A]]",
                "[[HasType::Category:B]]",
                "[[HasType::Category:C]]",
            ]
        ),
    )

    assert out == ["Item:OSW1", "Item:OSW3"]


def test_semantic_search_parallel_batch_with_one_zero_result_query():
    results = [
        _ask_result("Item:OSW1"),
        _ask_result("Item:OSW2"),
        _ask_result_empty(),
        _ask_result("Item:OSW4"),
        _ask_result("Item:OSW5"),
        _ask_result("Item:OSW6"),
    ]
    site = MagicMock()
    site.api.side_effect = results

    out = wt.semantic_search(
        site,
        wt.SearchParam(
            query=[
                "[[HasType::Category:A]]",
                "[[HasType::Category:B]]",
                "[[HasType::Category:C]]",
                "[[HasType::Category:D]]",
                "[[HasType::Category:E]]",
                "[[HasType::Category:F]]",
            ]
        ),
    )

    assert sorted(out) == [
        "Item:OSW1",
        "Item:OSW2",
        "Item:OSW4",
        "Item:OSW5",
        "Item:OSW6",
    ]


def test_semantic_search_truncation_warning():
    titles = [f"Item:OSW{i}" for i in range(5)]
    result = _ask_result(*titles)
    site = MagicMock()
    site.api.return_value = result

    with pytest.warns(UserWarning, match="truncated"):
        out = wt.semantic_search(
            site, wt.SearchParam(query="[[HasType::Category:Item]]", limit=5)
        )

    assert sorted(out) == sorted(titles)


def test_semantic_search_no_truncation_warning_below_limit():
    titles = [f"Item:OSW{i}" for i in range(5)]
    result = _ask_result(*titles)
    site = MagicMock()
    site.api.return_value = result

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = wt.semantic_search(
            site, wt.SearchParam(query="[[HasType::Category:Item]]", limit=1000)
        )

    assert not any("truncated" in str(w.message) for w in caught)
    assert sorted(out) == sorted(titles)


def test_semantic_search_exists_drop_warning():
    result = _ask_result("Item:OSW1", "Item:OSW2")
    result["query"]["results"]["Item:OSW2"]["exists"] = ""
    site = MagicMock()
    site.api.return_value = result

    with pytest.warns(UserWarning, match="non-existing"):
        out = wt.semantic_search(site, "[[HasType::Category:Item]]")

    assert out == ["Item:OSW1"]


def _prefixsearch_result(*titles):
    """Build a minimal MediaWiki ``prefixsearch`` API result dict."""
    return {
        "batchcomplete": "",
        "query": {
            "prefixsearch": [
                {"ns": 0, "title": title, "pageid": idx}
                for idx, title in enumerate(titles, start=1)
            ]
        },
    }


def test_prefix_search_return_json_single_query_returns_list_with_full_response():
    result = _prefixsearch_result("Star Wars", "Star Trek")
    site = MagicMock()
    site.api.return_value = result

    out = wt.prefix_search(site, wt.SearchParam(query="Star", return_json=True))

    # A single query returns a list of one full API response dict, not a flattened
    # list of individual prefixsearch entries
    assert isinstance(out, list)
    assert out == [result]
    assert out[0]["query"]["prefixsearch"][0]["title"] == "Star Wars"


def test_prefix_search_return_json_list_returns_list_of_full_responses():
    result_a = _prefixsearch_result("Star Wars")
    result_b = _prefixsearch_result("Voyager")
    site = MagicMock()
    site.api.side_effect = [result_a, result_b]

    out = wt.prefix_search(
        site, wt.SearchParam(query=["Star", "Voy"], return_json=True)
    )

    # One full API response dict per query, not merged/flattened across queries
    assert out == [result_a, result_b]


def test_prefix_search_returns_flat_list_of_titles():
    result = _prefixsearch_result("Star Wars", "Star Trek")
    site = MagicMock()
    site.api.return_value = result

    out = wt.prefix_search(site, "Star")

    # return_json=False (the default) still yields a flat list of page titles
    assert out == ["Star Wars", "Star Trek"]
