"""This script is meant to help with the migration of file pages from previous
versions to the current version of the OSW (xx and above).

Draft
-----
* Query OSW file pages -> namespace 'File'
* Query instances of WikiFile (Category:OSW11a53cdfbdc24524bf8ac435cbf65d9d) /
    see if jsondata slot
* Query OSW pages containing / referencing these files
* Remove instances of WikiFile from the results of the first query
* Process the remaining pages
    * generate uuid = new filename (with extension) etc. (wiki data class WikiFile)
    * label = original filename
        * use regex to get label from full page title
        * former structure = using page - file label
        * Default = Filename - suffix = label
        * Wenn kein Regex passt, dann label = filename
    * metadata (autor + Erstellseite aus template in main slot)
    * Move the file to the new location (rename)
    * Update the jsondata slot of the file page
    * Update calling templates
        * use mwparserfromhell to parse the template, update uuid

    Bisheriges Muster: File:NS-erstellerseite-name.extension

    wellplate.svg
    drawio.svg
    lucksheet.json
    kekule.json

use create_flat_content_structure_from_wikitext and
get_wikitext_from_flat_content_structure


Notes
-----
* Work with dask for the processing (but not for the queries)

"""
from pathlib import Path
from typing import List

import osw.wiki_tools as wt
from osw.data.mining import (
    RegExPatternExtended,
    match_first_regex_pattern,
    test_regex_pattern,
)
from osw.wiki_tools import SearchParam, get_file_info_and_usage
from osw.wtsite import WtSite

# Constants
PWD_FILE_PATH = Path(r"C:\Users\gold\ownCloud\Personal") / "accounts.pwd.yaml"
WIKIFILE_PAGE_NAME = "OSW11a53cdfbdc24524bf8ac435cbf65d9d"
REGEX_PATTERN_LIST = [
    RegExPatternExtended(
        description="File page full page title (new format) to label",
        pattern=r"File:(OS[WL]{1}[[a-f0-9]{32})"
        r"(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["Label", "Suffix(es)"],  # ["OSW-ID", "Suffix(es)"]
        example_str="File:OSW11a53cdfbdc24524bf8ac435cbf65d9d.svg",
    ),
    RegExPatternExtended(
        description="File page full page title (old format) with OSW-ID and two "
        "suffixes",
        pattern=r"File:([A-Za-z]+)[\- ]{1}(OS[WL]{1}[a-f0-9]{32})[\- ]{1}(.*)"
        r"(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*"
        r"\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["Namespace", "OSW-ID", "Label", "Suffix(es)"],
        example_str="File:LabNote-OSL9568a776dcdf4b7e86f462993df12059-"
        "spreadsheet-01.luckysheet.json",
    ),
    RegExPatternExtended(
        description="File page full page title (old format) with OSW-ID and one suffix",
        pattern=r"File:([A-Za-z]+)[\- ]{1}(OS[WL]{1}[a-f0-9]{32})[\- ]{1}(.*)"
        r"(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["Namespace", "OSW-ID", "Label", "Suffix(es)"],
        example_str="File:LabNote-OSL9ee686dbcc654f4abeaf5f38b8487885-sketch-05.svg",
    ),
    RegExPatternExtended(
        description="File page full page title (old format) with namespace, ISC-ID and "
        "two suffixes",
        pattern=r"File:([A-Za-z]+)[\- ]{1}([A-Za-z0-9\-]+[\- ]{1}[0-9]{4})[\- ]{1}(.*)"
        r"(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*"
        r"\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["Namespace", "ISC-ID", "Label", "Suffix(es)"],
        example_str="File:LabNote-220304-test-0002-ni-diagram-01.drawio.svg",
    ),
    RegExPatternExtended(
        description="File page full page title (old format) with namespace, ISC-ID and "
        "one suffix",
        pattern=r"File:([A-Za-z]+)[\- ]{1}([A-Za-z0-9\-]+[\- ]{1}[0-9]{4})[\- ]{1}(.*)"
        r"(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["Namespace", "ISC-ID", "Label", "Suffix(es)"],
        example_str="File:LabNote-220305-sist-0001-ni-sketch-furnace-black.svg",
    ),
    RegExPatternExtended(
        description="File page full page title (old format) with ISC-ID and two "
        "suffixes",
        pattern=r"File:([A-Za-z0-9\-]+[\- ]{1}[0-9]{4})[\- ]{1}(.*)"
        r"(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*"
        r"\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["ISC-ID", "Label", "Suffix(es)"],
        example_str="File:211104-sist-0003-n stamped 20211116080457.pdf.ots",
    ),
    RegExPatternExtended(
        description="File page full page title (old format) with ISC-ID and "
        "one suffix",
        pattern=r"File:([A-Za-z0-9\-]+[\- ]{1}[0-9]{4})[\- ]{1}(.*)"
        r"(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["ISC-ID", "Label", "Suffix(es)"],
        example_str="File:220304-test-0003-ni stamped 20220304155047.pdf",
    ),
    RegExPatternExtended(
        description="File page full page title with two suffixes",
        pattern=r"File:(.+)(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*"
        r"\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["Label", "Suffix(es)"],
        example_str="File:OpenSemanticLab-vertical-process-abstraction-en.drawio.svg",
    ),
    RegExPatternExtended(
        description="File page full page title with one suffix",
        pattern=r"File:(.+)(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["Label", "Suffix(es)"],
        example_str="File:ISC-Digital-1440x448px.jpg",
    ),
]
REGEX_PATTERN = {rep.description: rep.dict() for rep in REGEX_PATTERN_LIST}
REGEX_PATTERN_LIB = {rep.description: rep for rep in REGEX_PATTERN_LIST}
LABEL_REGEX_PATTERNS = [
    REGEX_PATTERN_LIB[key]
    for key in [
        "File page full page title (new format) to label",
        "File page full page title (old format) with OSW-ID and two suffixes",
        "File page full page title (old format) with OSW-ID and one suffix",
        "File page full page title (old format) with namespace, ISC-ID and two "
        "suffixes",
        "File page full page title (old format) with namespace, ISC-ID and one suffix",
        "File page full page title (old format) with ISC-ID and two suffixes",
        "File page full page title (old format) with ISC-ID and one suffix",
        "File page full page title with two suffixes",
        "File page full page title with one suffix",
    ]
]


# Functions
def get_label_and_suffix_from_page_title(page_title: str):
    match_res = match_first_regex_pattern(
        patterns=LABEL_REGEX_PATTERNS,
        strings=page_title,
    )
    if match_res[0].match is None:
        label = ""
        suffix = ""
    else:
        label = match_res[0].groups["Label"]
        suffix = match_res[0].groups["Suffix(es)"]
    return {"label": label, "suffix": suffix}


def get_file_info_and_usage_single(
    wtsite_obj: WtSite, page_title: str, debug: bool = False
) -> dict:
    result = get_file_info_and_usage(
        site=wtsite_obj._site,
        title=SearchParam(
            query=page_title,
            debug=debug,
        ),
    )[0]
    other_info = get_label_and_suffix_from_page_title(page_title=page_title)
    result["info"]["label"] = other_info["label"]
    result["info"]["suffix"] = other_info["suffix"]
    return result


def get_file_info_and_usage_(
    wt_site_obj: WtSite,
    page_titles: List[str],
    debug: bool = False,
) -> List[dict]:
    # result = wt_site_obj.get_file_info_and_usage(
    #     SearchParam(
    #         query=page_titles,
    #         debug=debug,
    #         parallel=True,
    #     )
    # )
    result = get_file_info_and_usage(
        site=wt_site_obj._site,
        title=SearchParam(
            query=page_titles,
            debug=debug,
            parallel=True,
        ),
    )
    if len(result) != len(page_titles):
        raise ValueError(
            f"Number of results ({len(result)}) does not match number of "
            f"page titles ({len(page_titles)})"
        )
    for i, page_tile in enumerate(page_titles):
        other_info = get_label_and_suffix_from_page_title(page_title=page_tile)
        result[i]["info"]["label"] = other_info["label"]
        result[i]["info"]["suffix"] = other_info["suffix"]
    return result


def get_wiki_file_pages(wtsite_obj: WtSite, limit: int = 1000) -> List[str]:
    # todo: move to osw.core.OSW as method
    # todo: rename with "get entity"
    # todo: replace with method
    full_page_titles = wt.semantic_search(
        site=wtsite_obj._site,
        query=wt.SearchParam(
            query=f"[[HasType::Category:{WIKIFILE_PAGE_NAME}]]",
            debug=False,
            limit=limit,
        ),
    )
    return full_page_titles


if __name__ == "__main__":
    patterns_to_test = LABEL_REGEX_PATTERNS
    wtsite = WtSite.from_domain(
        domain="wiki-dev.open-semantic-lab.org",
        password_file=PWD_FILE_PATH,
    )
    wiki_file_pages = get_wiki_file_pages(wtsite_obj=wtsite, limit=5000)  # replace with
    # OSW.get_instances_of(Cat:WIkiFile)
    file_pages = wtsite.get_file_pages()
    file_pages_to_modify = list(set(file_pages) - set(wiki_file_pages))
    print(f"Number of file pages to modify: {len(file_pages_to_modify)}")
    print("Collecting info and usage for file pages...")
    infos = get_file_info_and_usage_(
        wt_site_obj=wtsite,
        page_titles=file_pages_to_modify,
        debug=True,
    )

    regex_test = test_regex_pattern(patterns_to_test, file_pages_to_modify)
