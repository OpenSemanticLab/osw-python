import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) #add parent dir to path
import src.wiki_tools as wt 


def test_create_flat_content_structure_from_wikitext():
    wikitext = (
        "{{Template"
        "|param=value"
        "}}"
    )
    expected = [
        {"Template": {"param": ["value"]}}
    ]
    result = wt.create_flat_content_structure_from_wikitext(wikitext)
    assert result == expected
