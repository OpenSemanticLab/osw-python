from unittest.mock import MagicMock

import osw.wiki_tools as wt


def test_create_flat_content_structure_from_wikitext():
    wikitext = "{{Template" "|param=value" "}}"
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
