"""This script is meant to help with the migration of file pages from previous
versions to the current version of the OSW (xx and above)."""
import json
import uuid as uuid_module
from pathlib import Path
from typing import Dict, List

import mwclient

import osw.data.import_utility as iu
import osw.wiki_tools as wt
from osw.core import OSW
from osw.data.mining import (
    RegExPatternExtended,
    match_first_regex_pattern,
    test_regex_pattern,
)
from osw.model.entity import Label, WikiFile
from osw.utils.util import parallelize
from osw.wtsite import WtPage, WtSite

# Constants
PWD_FILE_PATH = Path(r"C:\Users\gold\ownCloud\Personal") / "accounts.pwd.yaml"
WIKIFILE_PAGE_NAME = "OSW11a53cdfbdc24524bf8ac435cbf65d9d"
WIKIFILE_NS = uuid_module.UUID(WIKIFILE_PAGE_NAME[3:])
REGEX_PATTERN_LIST = [
    RegExPatternExtended(
        description="File page full page title (new format) to label",
        pattern=r"File:(OS[WL]{1}[[a-f0-9]{32})"
        r"(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["Label", "Suffix(es)"],  # ["OSW-ID", "Suffix(es)"]
        example_str="File:OSW11a53cdfbdc24524bf8ac435cbf65d9d.svg",
        expected_groups=["OSW11a53cdfbdc24524bf8ac435cbf65d9d", ".svg"],
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
        expected_groups=[
            "LabNote",
            "OSL9568a776dcdf4b7e86f462993df12059",
            "spreadsheet-01",
            ".luckysheet.json",
        ],
    ),
    RegExPatternExtended(
        description="File page full page title (old format) with OSW-ID and one suffix",
        pattern=r"File:([A-Za-z]+)[\- ]{1}(OS[WL]{1}[a-f0-9]{32})[\- ]{1}(.*)"
        r"(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["Namespace", "OSW-ID", "Label", "Suffix(es)"],
        example_str="File:LabNote-OSL9ee686dbcc654f4abeaf5f38b8487885-sketch-05.svg",
        expected_groups=[
            "LabNote",
            "OSL9ee686dbcc654f4abeaf5f38b8487885",
            "sketch-05",
            ".svg",
        ],
    ),
    RegExPatternExtended(
        description="File page full page title (old format) with namespace, ISC-ID and "
        "two suffixes",
        pattern=r"File:([A-Za-z]+)[\- ]{1}([A-Za-z0-9\-]+[\- ]{1}[0-9]{4})[\- ]{1}(.*)"
        r"(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*"
        r"\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["Namespace", "ISC-ID", "Label", "Suffix(es)"],
        example_str="File:LabNote-220304-test-0002-ni-diagram-01.drawio.svg",
        expected_groups=["LabNote", "220304-test-0002", "ni-diagram-01", ".drawio.svg"],
    ),
    RegExPatternExtended(
        description="File page full page title (old format) with namespace, ISC-ID and "
        "one suffix",
        pattern=r"File:([A-Za-z]+)[\- ]{1}([A-Za-z0-9\-]+[\- ]{1}[0-9]{4})[\- ]{1}(.*)"
        r"(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["Namespace", "ISC-ID", "Label", "Suffix(es)"],
        example_str="File:LabNote-220305-sist-0001-ni-sketch-furnace-black.svg",
        expected_groups=[
            "LabNote",
            "220305-sist-0001",
            "ni-sketch-furnace-black",
            ".svg",
        ],
    ),
    RegExPatternExtended(
        description="File page full page title (old format) with ISC-ID and two "
        "suffixes",
        pattern=r"File:([A-Za-z0-9\-]+[\- ]{1}[0-9]{4})[\- ]{1}(.*)"
        r"(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*"
        r"\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["ISC-ID", "Label", "Suffix(es)"],
        example_str="File:211104-sist-0003-n stamped 20211116080457.pdf.ots",
        expected_groups=["211104-sist-0003", "n stamped 20211116080457", ".pdf.ots"],
    ),
    RegExPatternExtended(
        description="File page full page title (old format) with ISC-ID and "
        "one suffix",
        pattern=r"File:([A-Za-z0-9\-]+[\- ]{1}[0-9]{4})[\- ]{1}(.*)"
        r"(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["ISC-ID", "Label", "Suffix(es)"],
        example_str="File:220304-test-0003-ni stamped 20220304155047.pdf",
        expected_groups=["220304-test-0003", "ni stamped 20220304155047", ".pdf"],
    ),
    RegExPatternExtended(
        description="File page full page title with two suffixes",
        pattern=r"File:(.+)(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*"
        r"\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["Label", "Suffix(es)"],
        example_str="File:OpenSemanticLab-vertical-process-abstraction-en.drawio.svg",
        expected_groups=[
            "OpenSemanticLab-vertical-process-abstraction-en",
            ".drawio.svg",
        ],
    ),
    RegExPatternExtended(
        description="File page full page title with one suffix",
        pattern=r"File:(.+)(\.[a-zA-Z0-9]*[a-zA-Z]+[a-zA-Z0-9]*)",
        group_keys=["Label", "Suffix(es)"],
        example_str="File:ISC-Digital-1440x448px.jpg",
        expected_groups=["ISC-Digital-1440x448px", ".jpg"],
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
FILENAME_REGEX_PATTERNS = [
    REGEX_PATTERN_LIB[key]
    for key in [
        "File page full page title with two suffixes",
        "File page full page title with one suffix",
    ]
]


# Functions
def get_label_and_suffix_from_page_title(page_title: str) -> Dict[str, str]:
    match_res = match_first_regex_pattern(
        patterns=LABEL_REGEX_PATTERNS,
        strings=page_title,
    )
    id_ = ""
    label = ""
    suffix = ""
    if match_res[0].match is None:
        pass
    else:
        label = match_res[0].groups["Label"]
        suffix = match_res[0].groups["Suffix(es)"]
        for key in ["ISC-ID", "OSW-ID"]:
            val = match_res[0].groups.get(key, None)
            if val is not None:
                id_ = val
                break
    return {"label": label, "suffix": suffix, "id": id_}


def get_file_info_and_usage_single(
    wtsite_obj: WtSite, page_title: str, debug: bool = False
) -> dict:
    result = wt.get_file_info_and_usage(
        site=wtsite_obj._site,
        title=wt.SearchParam(
            query=page_title,
            debug=debug,
        ),
    )[0]
    other_info = get_label_and_suffix_from_page_title(page_title=page_title)
    result["info"]["label"] = other_info["label"]
    result["info"]["suffix"] = other_info["suffix"]
    result["info"]["id"] = other_info["id"]
    return result


def get_file_info_and_usage_extended(
    wtsite_obj: WtSite,
    page_titles: List[str],
    debug: bool = False,
    parallel: bool = True,
) -> List[dict]:
    result = wt.get_file_info_and_usage(
        site=wtsite_obj._site,
        title=wt.SearchParam(
            query=page_titles,
            debug=debug,
            parallel=parallel,
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
        result[i]["info"]["id"] = other_info["id"]
    return result


def move_file_pages_and_redirect_references(
    file_pages: List[str],
    wtsite_obj: WtSite,
    parallel: bool = True,
    debug: bool = False,
):
    def handle_single_using_page(
        full_page_title_: str,
        wtsite_obj_: WtSite,
        file_name_: str,
        uuid_: uuid_module.UUID,
    ):
        """Adds an uuid reference to the template of the using page's (main slot)
        content."""
        file_name_with_underscores_ = file_name_.replace(" ", "_")
        using_page = WtPage(wtSite=wtsite_obj_, title=full_page_title_)
        main_slot_content = using_page.get_slot_content(slot_key="main")
        parsed_content = wt.create_flat_content_structure_from_wikitext(
            main_slot_content
        )
        replaced = False
        # Loop through lines of the using page's content
        for ii, list_item in enumerate(parsed_content):
            if isinstance(list_item, dict):
                # Loop through template dict
                for template_key, template_val in list_item.items():
                    if isinstance(template_val, dict):
                        # Look for file_name key
                        # template_fn is of type list!
                        template_fn = template_val.get("file_name", None)
                        template_img = template_val.get("image", None)
                        # In case of a match, add uuid key with uuid value (new page
                        #  uuid)
                        if template_fn is not None:
                            if (
                                file_name_ in template_fn
                                or file_name_with_underscores_ in template_fn
                            ):
                                parsed_content[ii][template_key]["uuid"] = str(uuid_)
                                replaced = True
                        if template_img is not None:
                            if (
                                file_name_ in template_img
                                or file_name_with_underscores_ in template_img
                            ):
                                parsed_content[ii][template_key]["uuid"] = str(uuid_)
                                replaced = True
        modified_content = wt.get_wikitext_from_flat_content_structure(parsed_content)
        using_page.set_slot_content(slot_key="main", content=modified_content)
        using_page.edit(comment="Edited by bot to comply with new Wiki-File schema")
        return replaced

    def handle_single_file_page(file_info_: dict, wtsite_obj_: WtSite):
        info = file_info_["info"]
        usage = file_info_["usage"]
        id_str = info["id"]
        # Don't continue if there is no usage!
        if len(usage) != 0:
            page_title = file_info_["info"]["title"]
            file_page = WtPage(wtSite=wtsite_obj_, title=page_title)
            match_res = match_first_regex_pattern(
                patterns=REGEX_PATTERN_LIST,
                strings=page_title,
            )
            if match_res[0].match is None:
                raise ValueError(
                    f"Could not match page title '{page_title}' to any of the "
                    f"supported patterns"
                )
            else:
                file_name = match_res[0].groups["Label"]

            if len(usage) == 0:
                creation_context = ""
            else:
                creation_context = usage[0]
            if id_str != "":
                # try to find a page with the same id in the usage list
                for full_page_title in usage:
                    if id_str in full_page_title:
                        creation_context = full_page_title
                        break
            # Generate UUID for the new page name
            rnd_uuid = uuid_module.uuid4()
            uuid = uuid_module.uuid5(namespace=WIKIFILE_NS, name=str(rnd_uuid))
            # Generate full page title from UUID
            new_fpt_without_suffix = iu.uuid_to_full_page_title(
                uuid=uuid, wiki_ns="File", prefix="OSW"
            )
            new_fpt = new_fpt_without_suffix + info["suffix"]

            # Loop through using pages - check if the script covers the use case of
            #  at least on using page
            covered = False
            for full_page_title in usage:
                ret_val = handle_single_using_page(
                    full_page_title_=full_page_title,
                    wtsite_obj_=wtsite_obj_,
                    file_name_=file_name,
                    uuid_=uuid,
                )
                if ret_val:
                    covered = True
            # Only move the page if the use case was covered
            if covered:
                # Rename the page
                # file_page.move(new_title=new_fpt, redirect=False)
                try:
                    file_page.move(new_title=new_fpt, redirect=False)
                except mwclient.APIError as e:
                    if e.code == "badtoken":
                        print("Got badtoken, retrying")
                        # wtsite_obj_.clear_token_cache()
                        file_page.move(new_title=new_fpt, redirect=False)  # retry

                # Make sure the slot content to be set is in accordance with the JSON
                #  schema of the category
                wiki_file_instance = WikiFile(
                    uuid=uuid,
                    label=[Label(text=info["label"])],
                    creator=[info["author"]],
                    creation_context=[creation_context],
                    # todo: new filename here? -> Name?
                    name=iu.create_page_name_from_label(label=info["label"]),
                    editor=info["editor"],
                    editing_context=usage,
                )
                # Get jsondata for the new wiki file page from the WikiFile instance
                #  with dict() or json()
                jsondata = json.loads(wiki_file_instance.json())
                file_page.set_slot_content(slot_key="jsondata", content=jsondata)
                file_page.set_slot_content(
                    "header", "{{#invoke:Entity|header}}"
                )  # required for json parsing and header rendering
                file_page.set_slot_content(
                    "footer", "{{#invoke:Entity|footer}}"
                )  # required for footer rendering
                # Actually edit the page in the OSL instance
                file_page.edit(
                    comment="Edited by bot to comply with new Wiki-File schema"
                )
                # # Alternatively, use the following to edit the page in the OSL
                # #  instance
                # osw_obj = OSW(site=wtsite_obj_)
                # osw_obj.store_entity(OSW.StoreEntityParam(
                #     entities=[wiki_file_instance], namespace="File"
                # ))
            return new_fpt

    # This is executed in parallel first (!)
    file_infos = get_file_info_and_usage_extended(
        wtsite_obj=wtsite_obj,
        page_titles=file_pages,
        debug=debug,
        parallel=parallel,
    )
    # Loop through file_pages
    if parallel:
        result = parallelize(
            handle_single_file_page,
            file_infos,
            wtsite_obj_=wtsite_obj,
            flush_at_end=debug,
        )
    else:
        result = []
        for fi in file_infos:
            result.append(
                handle_single_file_page(file_info_=fi, wtsite_obj_=wtsite_obj)
            )
    return result


def get_wiki_file_pages(wtsite_obj: WtSite, limit: int = 1000) -> List[str]:
    full_page_titles = OSW(site=wtsite_obj).query_instances(
        category=OSW.QueryInstancesParam(
            categories=[WIKIFILE_PAGE_NAME],
            limit=limit,
        )
    )
    return full_page_titles


def validation():
    patterns_to_test = LABEL_REGEX_PATTERNS
    wtsite = WtSite.from_domain(
        domain="wiki-dev.open-semantic-lab.org",
        password_file=PWD_FILE_PATH,
    )
    wiki_file_pages = get_wiki_file_pages(wtsite_obj=wtsite, limit=5000)  # replace with
    # OSW.get_instances_of(Cat:WIkiFile)
    file_pages_ = wtsite.get_file_pages()
    file_pages_to_modify = list(set(file_pages_) - set(wiki_file_pages))
    print("Collecting info and usage for file pages...")
    file_infos = get_file_info_and_usage_extended(
        wtsite_obj=wtsite,
        page_titles=file_pages_to_modify,
        debug=False,
        parallel=True,
    )

    regex_test = test_regex_pattern(patterns_to_test, file_pages_to_modify)
    return file_infos, regex_test


def main(number_of_pages_to_process: int = None):
    wtsite = WtSite.from_domain(
        domain="wiki-dev.open-semantic-lab.org",
        password_file=PWD_FILE_PATH,
    )
    wiki_file_pages = get_wiki_file_pages(wtsite_obj=wtsite, limit=5000)  # replace with
    # OSW.get_instances_of(Cat:WIkiFile)
    file_pages_ = wtsite.get_file_pages()
    file_pages_to_modify = list(set(file_pages_) - set(wiki_file_pages))
    print(f"Number of file pages to modify: {len(file_pages_to_modify)}")
    if number_of_pages_to_process is None:
        move_file_pages_and_redirect_references(
            file_pages_to_modify, wtsite, parallel=True
        )
    else:
        move_file_pages_and_redirect_references(
            file_pages_to_modify[:number_of_pages_to_process], wtsite, parallel=True
        )


if __name__ == "__main__":
    main()
