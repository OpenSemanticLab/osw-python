import warnings
from unittest.mock import MagicMock

import pytest

import osw.wiki_tools as wt


def test_create_flat_content_structure_from_wikitext():
    wikitext = "{{Template|param=value}}"
    expected = [{"Template": {"param": ["value"]}}]
    result = wt.create_flat_content_structure_from_wikitext(wikitext)
    assert result == expected


def test_read_domains_from_credentials_file_empty_file_raises_value_error(tmp_path):
    """An empty file is parsed as None by yaml.safe_load. Before the fix this
    raised an unhandled AttributeError from accounts_dict.keys(); it must now
    raise the same clear ValueError as an empty mapping."""
    cred_file = tmp_path / "accounts.pwd.yaml"
    cred_file.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="No domain found"):
        wt.read_domains_from_credentials_file(cred_file)


def test_read_domains_from_credentials_file_empty_mapping_raises_value_error(
    tmp_path,
):
    cred_file = tmp_path / "accounts.pwd.yaml"
    cred_file.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="No domain found"):
        wt.read_domains_from_credentials_file(cred_file)


def test_read_domains_from_credentials_file_valid_file_returns_domains_and_accounts(
    tmp_path,
):
    cred_file = tmp_path / "accounts.pwd.yaml"
    cred_file.write_text(
        "example.org:\n  username: user\n  password: pass\n", encoding="utf-8"
    )

    domains, accounts = wt.read_domains_from_credentials_file(cred_file)

    assert domains == ["example.org"]
    assert accounts == {"example.org": {"username": "user", "password": "pass"}}


def _ask_result(*titles, continue_offset=None):
    """Build a minimal SMW ``ask`` API result dict for the given page titles.

    ``continue_offset`` adds the top-level ``query-continue-offset`` key that SMW
    sends when further results exist beyond the ones returned."""
    result = {
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
    if continue_offset is not None:
        result["query-continue-offset"] = continue_offset
    return result


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
    result = _ask_result(*titles, continue_offset=5)
    site = MagicMock()
    site.api.return_value = result

    with pytest.warns(UserWarning, match="truncated"):
        out = wt.semantic_search(
            site, wt.SearchParam(query="[[HasType::Category:Item]]", limit=5)
        )

    assert sorted(out) == sorted(titles)


def test_semantic_search_no_truncation_warning_for_a_complete_set_at_the_limit():
    """A wiki that has exactly as many results as the limit asked for sends no
    offset, so meeting the limit is not on its own a sign of truncation."""
    titles = [f"Item:OSW{i}" for i in range(5)]
    site = MagicMock()
    site.api.return_value = _ask_result(*titles)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = wt.semantic_search(
            site, wt.SearchParam(query="[[HasType::Category:Item]]", limit=5)
        )

    assert not any("truncated" in str(w.message) for w in caught)
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


def test_semantic_search_truncation_warning_from_the_continue_offset():
    # Fewer results than the limit, so only the wiki's own signal can report
    # that the result set was cut short
    result = _ask_result("Item:OSW1", "Item:OSW2", continue_offset=2)
    site = MagicMock()
    site.api.return_value = result

    with pytest.warns(UserWarning, match="truncated"):
        out = wt.semantic_search(
            site, wt.SearchParam(query="[[HasType::Category:Item]]", limit=1000)
        )

    assert sorted(out) == ["Item:OSW1", "Item:OSW2"]


def test_semantic_search_limit_none_warns_from_the_continue_offset():
    # With no limit in force the wiki applies its own '$smwgQMaxLimit' cap,
    # which the result count cannot detect
    result = _ask_result("Item:OSW1", "Item:OSW2", continue_offset=2)
    site = MagicMock()
    site.api.return_value = result

    with pytest.warns(UserWarning, match="truncated"):
        wt.semantic_search(
            site, wt.SearchParam(query="[[HasType::Category:Item]]", limit=None)
        )


def test_semantic_search_return_json_keeps_the_continue_offset():
    result = _ask_result("Item:OSW1", continue_offset=1)
    site = MagicMock()
    site.api.return_value = result

    with pytest.warns(UserWarning, match="truncated"):
        out = wt.semantic_search(
            site, wt.SearchParam(query="[[HasType::Category:Item]]", return_json=True)
        )

    # The raw response is returned unchanged, so it already carries the
    # truncation signal
    assert out[0]["query-continue-offset"] == 1


def test_semantic_search_return_meta_reports_truncation():
    result = _ask_result("Item:OSW1", "Item:OSW2", continue_offset=2)
    site = MagicMock()
    site.api.return_value = result

    with pytest.warns(UserWarning, match="truncated"):
        out = wt.semantic_search(
            site, wt.SearchParam(query="[[HasType::Category:Item]]", return_meta=True)
        )

    assert len(out) == 1
    assert isinstance(out[0], wt.SemanticSearchResult)
    assert out[0].truncated is True
    assert out[0].next_offset == 2
    assert out[0].count == 2
    assert sorted(out[0].titles) == ["Item:OSW1", "Item:OSW2"]
    # the limit appended by semantic_search is part of the reported query
    assert out[0].query == "[[HasType::Category:Item]]|limit=1000"


def test_semantic_search_return_meta_reports_a_complete_result():
    result = _ask_result("Item:OSW1", "Item:OSW2")
    site = MagicMock()
    site.api.return_value = result

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = wt.semantic_search(
            site, wt.SearchParam(query="[[HasType::Category:Item]]", return_meta=True)
        )

    assert not any("truncated" in str(w.message) for w in caught)
    assert out[0].truncated is False
    assert out[0].next_offset is None
    assert out[0].count == 2


def test_semantic_search_return_meta_returns_one_result_per_query():
    site = MagicMock()
    site.api.side_effect = [
        _ask_result("Item:OSW1", continue_offset=1),
        _ask_result("Item:OSW2"),
    ]

    with pytest.warns(UserWarning, match="truncated"):
        out = wt.semantic_search(
            site,
            wt.SearchParam(
                query=["[[HasType::Category:A]]", "[[HasType::Category:B]]"],
                return_meta=True,
            ),
        )

    # One entry per query, not flattened into a single list of titles
    assert len(out) == 2
    assert [r.truncated for r in out] == [True, False]
    assert [r.titles for r in out] == [["Item:OSW1"], ["Item:OSW2"]]


def test_semantic_search_return_meta_count_includes_dropped_pages():
    result = _ask_result("Item:OSW1", "Item:OSW2")
    result["query"]["results"]["Item:OSW2"]["exists"] = ""
    site = MagicMock()
    site.api.return_value = result

    with pytest.warns(UserWarning, match="non-existing"):
        out = wt.semantic_search(
            site, wt.SearchParam(query="[[HasType::Category:Item]]", return_meta=True)
        )

    assert out[0].count == 2
    assert out[0].titles == ["Item:OSW1"]


def test_semantic_search_return_meta_keeps_the_query_order_when_parallel():
    # More than five queries makes SearchParam switch to the parallel path, where
    # the results must still line up with the queries they came from
    queries = [f"[[HasType::Category:C{i}]]" for i in range(6)]

    def api(action, query=None, format=None):
        index = queries.index(query.split("|limit=")[0])
        return _ask_result(f"Item:OSW{index}", continue_offset=index or None)

    site = MagicMock()
    site.api.side_effect = api
    param = wt.SearchParam(query=queries, return_meta=True)
    assert param.parallel is True

    with pytest.warns(UserWarning, match="truncated"):
        out = wt.semantic_search(site, param)

    assert [r.query.split("|limit=")[0] for r in out] == queries
    assert [r.titles for r in out] == [[f"Item:OSW{i}"] for i in range(6)]
    assert [r.truncated for r in out] == [False] + [True] * 5


def test_semantic_search_return_json_takes_precedence_over_return_meta():
    result = _ask_result("Item:OSW1")
    site = MagicMock()
    site.api.return_value = result

    out = wt.semantic_search(
        site,
        wt.SearchParam(
            query="[[HasType::Category:Item]]", return_json=True, return_meta=True
        ),
    )

    assert out == [result]


@pytest.mark.parametrize(
    "query, expected",
    [
        ("[[HasType::Category:Item]]", None),
        ("[[HasType::Category:Item]]|limit=2", 2),
        ("[[HasType::Category:Item]]|?Name|limit=2|offset=5", 2),
        ("[[HasType::Category:Item]]| limit = 2 ", 2),
        ("[[HasType::Category:Item]]|Limit=2", 2),
        # SMW honours the last one, so that is the effective limit
        ("[[HasType::Category:Item]]|limit=2|limit=7", 7),
        # a limit inside a condition is a value, not a parameter
        ("[[HasText::limit=2]]", None),
        ("[[HasText::a||limit=2]]", None),
        # a printout named 'limit', not the parameter
        ("[[HasType::Category:Item]]|?limit", None),
        # a printout parameter, which limits that printout and not the query
        ("[[HasType::Category:Item]]|?Has subobject|+limit=3", None),
        # not a number, so there is no limit to honour
        ("[[HasType::Category:Item]]|limit=all", None),
    ],
)
def test_get_query_limit(query, expected):
    assert wt.get_query_limit(query) == expected


def test_semantic_search_appends_the_default_limit():
    site = MagicMock()
    site.api.return_value = _ask_result("Item:OSW1")

    wt.semantic_search(site, "[[HasType::Category:Item]]")

    assert site.api.call_args.kwargs["query"] == (
        "[[HasType::Category:Item]]|limit=1000"
    )


def test_semantic_search_keeps_a_limit_the_caller_wrote():
    """Appending the default would override it, since SMW honours the last one."""
    site = MagicMock()
    site.api.return_value = _ask_result("Item:OSW1")

    wt.semantic_search(site, "[[HasType::Category:Item]]|limit=2")

    assert site.api.call_args.kwargs["query"] == "[[HasType::Category:Item]]|limit=2"


def test_semantic_search_query_limit_beats_the_search_param_limit():
    site = MagicMock()
    site.api.return_value = _ask_result("Item:OSW1")

    wt.semantic_search(
        site, wt.SearchParam(query="[[HasType::Category:Item]]|limit=2", limit=500)
    )

    assert site.api.call_args.kwargs["query"] == "[[HasType::Category:Item]]|limit=2"


def test_semantic_search_truncation_warning_names_the_query_as_sent():
    """The caller's limit is the one the results were truncated at, so the
    warning has to quote the query carrying it."""
    titles = [f"Item:OSW{i}" for i in range(2)]
    site = MagicMock()
    site.api.return_value = _ask_result(*titles, continue_offset=2)

    with pytest.warns(UserWarning, match=r"\|limit=2'"):
        out = wt.semantic_search(site, "[[HasType::Category:Item]]|limit=2")

    assert sorted(out) == sorted(titles)


def test_semantic_search_limit_none_sends_no_limit():
    """None asks for no limit at all, leaving the wiki to apply its own."""
    site = MagicMock()
    site.api.return_value = _ask_result("Item:OSW1")

    wt.semantic_search(
        site, wt.SearchParam(query="[[HasType::Category:Item]]", limit=None)
    )

    assert site.api.call_args.kwargs["query"] == "[[HasType::Category:Item]]"


def test_semantic_search_limit_none_keeps_a_limit_the_caller_wrote():
    site = MagicMock()
    site.api.return_value = _ask_result("Item:OSW1")

    wt.semantic_search(
        site, wt.SearchParam(query="[[HasType::Category:Item]]|limit=2", limit=None)
    )

    assert site.api.call_args.kwargs["query"] == "[[HasType::Category:Item]]|limit=2"


def test_semantic_search_limit_none_does_not_warn_without_an_offset():
    """A wiki reporting no further results never triggers the warning, whatever
    limit was in force."""
    titles = [f"Item:OSW{i}" for i in range(5)]
    site = MagicMock()
    site.api.return_value = _ask_result(*titles)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = wt.semantic_search(
            site, wt.SearchParam(query="[[HasType::Category:Item]]", limit=None)
        )

    assert not any("truncated" in str(w.message) for w in caught)
    assert sorted(out) == sorted(titles)


def test_semantic_search_no_truncation_warning_for_a_zero_limit():
    """'limit=0' asks for a count rather than results, and SMW sends no offset
    for it even when the query does match pages."""
    site = MagicMock()
    site.api.return_value = _ask_result_empty()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        wt.semantic_search(site, "[[HasType::Category:Item]]|limit=0")

    assert not any("truncated" in str(w.message) for w in caught)


def test_semantic_search_no_truncation_warning_below_the_query_limit():
    titles = [f"Item:OSW{i}" for i in range(2)]
    site = MagicMock()
    site.api.return_value = _ask_result(*titles)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        wt.semantic_search(site, "[[HasType::Category:Item]]|limit=50")

    assert not any("truncated" in str(w.message) for w in caught)


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
