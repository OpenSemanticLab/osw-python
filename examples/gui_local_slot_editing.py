"""This script provides a GUI for downloading an OSW instances page slots, editing
them locally and uploading them again."""
import json
import os

# import yaml
from pathlib import Path
from typing import Union

import PySimpleGUI as psg
from numpy import array as np_array

import osw.model.page_package as package
from osw.core import OSW
from osw.wiki_tools import read_domains_from_credentials_file
from osw.wtsite import SLOTS, WtPage, WtSite

# Definition of constants
GUI_THEME = "reddit"
DEBUG = True  # Set to True to get an output element in the GUI
DUMP_EMPTY_SLOTS_DEFAULT = True
SEL_INDICES_DEFAULT = [
    0,  # "main",
    3,  # "jsondata",
    4,  # "jsonschema",
    6,  # "header_template",
]
SLOTS_TO_UPLOAD_DEFAULT = np_array(list(SLOTS.keys()))[SEL_INDICES_DEFAULT].tolist()
TARGET_PAGE_DEFAULT = "https://wiki-dev.open-semantic-lab.org/wiki/Main_Page"
LWD_DEFAULT = Path(os.getcwd()).parent / "data"
SETTINGS_FILE_PATH_DEFAULT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "settings.json"
)
CREDENTIALS_FILE_PATH_DEFAULT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)
PACKAGE_INFO_FILE_NAME = "packages.json"
# Sub folder to store the slot content of the page in. If None, the content is stored
#  in the root folder alongside the package info file.
SUB_LEVEL = None  # "content"
# Whether to store the page content in a sub folder named after the namespace
NAMESPACE_AS_FOLDER = False


# Definition of functions
def str_or_none(value):
    if str(value) == "" or value is None:
        return str("None")
    else:
        return str(value)


def create_config_from_setting(settings_: dict) -> WtPage.PageDumpConfig:
    config_ = WtPage.PageDumpConfig(
        target_dir=settings_["local_working_directory"],
        namespace_as_folder=settings_["namespace_as_folder"],
        dump_empty_slots=settings_["dump_empty_slots"],
        page_name_as_filename=settings_["page_name_as_filename"],
    )
    return config_


def save_as_page_package(
    full_page_name_str,
    wtsite_inst: WtSite,
    dump_config_inst: WtPage.PageDumpConfig,
    label_str: str = None,
    top_level: str = None,
    sub_level: str = None,  # "content"
    author: Union[str, list] = "Open Semantic World",
):
    if top_level is None:
        top_level = full_page_name_str.split(":")[-1]
    package_repo_org = "OpenSemanticWorld-Packages"
    package_repo = f"{top_level}.{sub_level}"
    package_id = f"{top_level}.{sub_level}"
    package_name = top_level
    package_subdir = sub_level
    package_branch = "deleteme"
    publisher = "Open Semantic World"
    working_dir = dump_config_inst.target_dir
    if dump_config_inst.page_name_as_filename and label_str is not None:
        target_dir = os.path.join(working_dir, label_str)
    else:
        target_dir = os.path.join(working_dir, top_level)
    if isinstance(author, list):
        author_list = author
    elif isinstance(author, str):
        author_list = [author]
    else:
        author_list = [""]
    if package_subdir is None:
        base_url = (
            f"https://raw.githubusercontent.com/{package_repo_org}/"
            f"{package_repo}/{package_branch}/"
        )
        content_path = target_dir
    else:
        base_url = (
            f"https://raw.githubusercontent.com/{package_repo_org}/"
            f"{package_repo}/{package_branch}/{package_subdir}/"
        )
        content_path = os.path.join(target_dir, package_subdir)
    bundle = package.PagePackageBundle(
        publisher=publisher,
        author=author_list,
        language="en",
        publisherURL=f"https://github.com/{package_repo_org}/{package_repo}",
        packages={
            f"{package_name}": package.PagePackage(
                globalID=f"{package_id}",
                label=package_name,
                version="0.0.1",
                description="Created by the GUI for local editing of OSW pages",
                baseURL=base_url,
            )
        },
    )
    config = package.PagePackageConfig(
        name=package_name,
        config_path=os.path.join(target_dir, PACKAGE_INFO_FILE_NAME),
        content_path=content_path,
        bundle=bundle,
        titles=[full_page_name_str],
    )
    wtsite_inst.create_page_package(
        WtSite.CreatePagePackageParam(
            config=config,
            dump_config=dump_config_inst,
            debug=False,
        )
    )
    return {"Page package bundle": bundle, "Page package config": config}


if __name__ == "__main__":
    # Predefining some variables before execution
    settings_file_path = SETTINGS_FILE_PATH_DEFAULT
    if os.path.exists(settings_file_path):
        with open(settings_file_path, "r") as f:
            settings = json.load(f)
        settings_read_from_file = True
    else:
        settings = {
            "credentials_file_path": str(CREDENTIALS_FILE_PATH_DEFAULT),
            "local_working_directory": str(LWD_DEFAULT),
            "settings_file_path": str(SETTINGS_FILE_PATH_DEFAULT),
            "target_page": TARGET_PAGE_DEFAULT,
            "namespace_as_folder": NAMESPACE_AS_FOLDER,
            "dump_empty_slots": DUMP_EMPTY_SLOTS_DEFAULT,
            "page_name_as_filename": True,
            "slots_to_upload": SLOTS_TO_UPLOAD_DEFAULT,
            "domain": "",
        }
        settings_read_from_file = False

    domains, accounts = read_domains_from_credentials_file(
        settings["credentials_file_path"]
    )
    if "wiki-dev.open-semantic-lab.org" in domains:
        domain = "wiki-dev.open-semantic-lab.org"
    else:
        domain = domains[0]
    if settings_read_from_file:
        settings["domain"] = domain

    wtsite_obj = WtSite.from_domain(
        domain=domain, password_file="", credentials=accounts[domain]
    )
    osw_obj = OSW(site=wtsite_obj)

    full_page_name = settings["target_page"].split("/")[-1].replace("_", " ")
    page = wtsite_obj.get_WtPage(full_page_name)
    label_set = False
    label = None
    slots_downloaded = False
    dump_config = create_config_from_setting(settings)

    # ----- GUI Definition -----
    # Setting the theme of the GUI
    psg.theme(GUI_THEME)
    # Settings
    settings_layout = [
        [psg.Text("Settings", font=("Helvetica", 20))],
        [
            psg.Column(
                [
                    [
                        psg.Text("Settings file"),
                    ],
                    [
                        psg.Text("Credentials file"),
                    ],
                    [
                        psg.Text("Local working directory"),
                    ],
                ]
            ),
            psg.Column(
                [
                    [
                        psg.In(
                            size=(50, 1),
                            enable_events=True,
                            key="-SETTINGS-",
                            default_text=settings["settings_file_path"],
                        ),
                        psg.FileBrowse(button_text="Browse", key="-BROWSE_SETTINGS-"),
                        psg.Button("Load", key="-LOAD_SETTINGS-"),
                        psg.Button("Save", key="-SAVE_SETTINGS-"),
                    ],
                    [
                        psg.In(
                            size=(50, 1),
                            enable_events=True,
                            key="-CREDENTIALS-",
                            default_text=settings["credentials_file_path"],
                        ),
                        psg.FileBrowse(
                            button_text="Browse", key="-BROWSE_CREDENTIALS-"
                        ),
                    ],
                    [
                        psg.In(
                            size=(50, 1),
                            enable_events=True,
                            key="-LWD-",
                            default_text=settings["local_working_directory"],
                        ),
                        psg.FolderBrowse(button_text="Browse", key="-BROWSE_LWD-"),
                    ],
                ]
            ),
        ],
        [psg.HSeparator()],
    ]
    # Actions
    actions_layout = [
        # Actions
        [psg.Text("Actions", font=("Helvetica", 20))],
        # Target OSW instance
        [psg.Text("Target OSW instance", font=("Helvetica", 16))],
        [psg.Text("List of domains is read from accounts.pwd.yaml!")],
        [psg.Combo(domains, default_value=domain, key="-DOMAIN-", enable_events=True)],
        # Target page
        [psg.Text("Target page", font=("Helvetica", 16))],
        [
            psg.Column(
                [
                    [psg.Text("Address, within selected OSW instance")],
                    [psg.Text("First label of the OSW page:")],
                ]
            ),
            psg.Column(
                [
                    [
                        psg.InputText(
                            size=(50, 1),
                            default_text=settings["target_page"],
                            key="-ADDRESS-",
                        ),
                        psg.Button("Load page"),
                    ],
                    [
                        # A display element that will show the label of the OSW page
                        psg.Multiline(size=(50, 1), key="-LABEL-", no_scrollbar=True)
                    ],
                ]
            ),
        ],
        # [
        #     psg.HSeparator()
        # ],
        # Slots to download
        [psg.Text("Slots to download", font=("Helvetica", 16))],
        [
            psg.Column(
                [
                    [
                        psg.Radio(
                            "Include empty slots",
                            group_id="-RADIO1-",
                            default=settings["dump_empty_slots"],
                            key="-INC_EMPTY-",
                            enable_events=True,
                        )
                    ],
                    [
                        psg.Radio(
                            "Exclude empty slots",
                            group_id="-RADIO1-",
                            default=(not settings["dump_empty_slots"]),
                            key="-EXC_EMPTY-",
                            enable_events=True,
                        )
                    ],
                    [psg.Button("Download selected", key="-DL-")],
                    [psg.Multiline(size=(20, 1), key="-DL_RES-", no_scrollbar=True)],
                ]
            ),
        ],
        # [
        #     psg.HSeparator()
        # ],
        # Slots to upload
        [psg.Text("Slots to upload", font=("Helvetica", 16))],
        [
            psg.Column(
                [
                    [psg.Button("(De)Select all", key="-UL_SEL-")],
                    [
                        psg.Listbox(
                            values=SLOTS.keys(),
                            default_values=settings["slots_to_upload"],
                            size=(20, 10),
                            key="-UL_LIST-",
                            select_mode=psg.LISTBOX_SELECT_MODE_MULTIPLE,
                            enable_events=True,
                            no_scrollbar=True,
                        )
                    ],
                    [psg.Button("Upload selected", key="-UL-")],
                    [psg.Multiline(size=(20, 1), key="-UL_RES-", no_scrollbar=True)],
                ]
            )
        ],
    ]
    output_layout = [
        [psg.HSeparator()],
        # Output
        [psg.Text("Debug output", font=("Helvetica", 20))],
        [psg.Multiline(key="-OUTPUT-", size=(100, 10))],
    ]
    # The full layout
    layout = settings_layout + actions_layout
    if DEBUG:
        layout += output_layout
    # Create the window
    window = psg.Window("OSW local editing GUI", layout)
    # Create an event loop
    while True:
        event, values = window.read()
        # End program if user closes window or
        # presses the OK button
        if event == "OK" or event == psg.WIN_CLOSED:
            break
        elif event == "-SETTINGS-":
            settings["settings_file_path"] = values["-SETTINGS-"]
        elif event == "-LOAD_SETTINGS-":
            # update settings
            with open(settings["settings_file_path"], "r") as f:
                settings = json.load(f)
            # update GUI
            window["-CREDENTIALS-"].update(settings["credentials_file_path"]),
            window["-LWD-"].update(settings["local_working_directory"])
            window["-DOMAIN-"].update(settings["domain"])
            window["-ADDRESS-"].update(settings["target_page"])
            window["-INC_EMPTY-"].update(settings["dump_empty_slots"])
            window["-EXC_EMPTY-"].update(not settings["dump_empty_slots"])
            indices = [
                i
                for i, x in enumerate(SLOTS.keys())
                if x in settings["slots_to_upload"]
            ]
            window["-UL_LIST-"].update(set_to_index=indices)
            settings_read_from_file = True
        elif event == "-SAVE_SETTINGS-":
            with open(settings["settings_file_path"], "w") as f:
                json.dump(settings, f, indent=4)
        elif event == "-CREDENTIALS-":
            settings["credentials_file_path"] = values["-CREDENTIALS-"]
            domains, accounts = read_domains_from_credentials_file(
                settings["credentials_file_path"]
            )
            window["-DOMAIN-"].update(values=domains)
        elif event == "-LWD-":
            settings["local_working_directory"] = values["-LWD-"]
        elif event == "-DOMAIN-":
            settings["domain"] = values["-DOMAIN-"]
            domain = settings["domain"].split("//")[-1]
            wtsite_obj = WtSite.from_domain(
                domain=settings["domain"],
                password_file="",
                credentials=accounts[settings["domain"]],
            )
            osw_obj = OSW(site=wtsite_obj)
        elif event == "Load page":
            window["-LABEL-"].update("Loading page...")
            window["-DL_RES-"].update("")
            full_page_name = values["-ADDRESS-"].split("/")[-1].replace("_", " ")
            if (values["-ADDRESS-"].find("/wiki/") != -1) or (
                values["-ADDRESS-"].find("/w/") != -1
            ):
                settings["target_page"] = values["-ADDRESS-"]
            else:
                settings["target_page"] = (
                    "https://" + domain + "/wiki/" + full_page_name
                )
            if values["-ADDRESS-"].find(settings["domain"]) == -1:
                window["-LABEL-"].update("Page not on selected domain!")
                label_set = False
            else:
                # use connection
                page = wtsite_obj.get_WtPage(full_page_name)
                if page.exists:
                    jsondata = page.get_slot_content("jsondata")
                    if jsondata is None:
                        window["-LABEL-"].update("Slot 'jsondata' is empty!")
                        label_set = False
                    else:
                        label = jsondata["label"][0]["text"]
                        window["-LABEL-"].update(label)
                        label_set = True
                else:
                    window["-LABEL-"].update("Page does not exist!")
                    label_set = False
        elif event == "-EXC_EMPTY-" or event == "-INC_EMPTY-":
            settings["dump_empty_slots"] = values["-INC_EMPTY-"]
        elif event == "-DL-":
            window["-DL_RES-"].update("Downloading slots...")
            if label_set:
                dump_config = create_config_from_setting(settings)
                _ = save_as_page_package(
                    full_page_name_str=full_page_name,
                    wtsite_inst=wtsite_obj,
                    dump_config_inst=dump_config,
                    label_str=label,
                    sub_level=SUB_LEVEL,
                    author=accounts[domains[0]]["username"],
                )
                slots_downloaded = True
                window["-DL_RES-"].update("Slots downloaded!")
            else:
                window["-DL_RES-"].update("No page loaded!")
        elif event == "-UL_SEL-":
            indices = list(window["-UL_LIST-"].get_indexes())
            # All selected: deselect all
            if indices == list(range(len(SLOTS.keys()))):
                window["-UL_LIST-"].update(set_to_index=[])
                settings["slots_to_upload"] = []
            else:
                window["-UL_LIST-"].update(set_to_index=list(range(len(SLOTS.keys()))))
                settings["slots_to_upload"] = list(SLOTS.keys())
        elif event == "-UL_LIST-":
            indices = list(window["-UL_LIST-"].get_indexes())
            settings["slots_to_upload"] = np_array(list(SLOTS.keys()))[indices].tolist()
        elif event == "-UL-":
            slots_to_upload = settings["slots_to_upload"]
            if not label_set:
                window["-UL_RES-"].update("No page loaded!")
            elif len(slots_to_upload) == 0:
                window["-UL_RES-"].update("No slots selected!")
            else:
                if not slots_downloaded:
                    window["-UL_RES-"].update("No slots downloaded!")
                    dump_config = create_config_from_setting(settings)
                window["-UL_RES-"].update("Uploading slots...")
                if SUB_LEVEL is None:
                    storage_path = Path(dump_config.target_dir)
                else:
                    storage_path = Path(dump_config.target_dir).parent
                pages = wtsite_obj.read_page_package(
                    WtSite.ReadPagePackageParam(
                        storage_path=storage_path,
                        packages_info_file_name=PACKAGE_INFO_FILE_NAME,
                        selected_slots=slots_to_upload,
                        debug=False,
                    )
                ).pages
                param = wtsite_obj.UploadPageParam(pages=pages, parallel=False)
                wtsite_obj.upload_page(param)
                # Success:
                window["-UL_RES-"].update("Slots uploaded!")
                # Report in the download section that the slots have been uploaded to
                #  remind the user that he eventually has to re-download the slots
                window["-DL_RES-"].update("Slots uploaded!")

        # Some debugging output functionality
        if DEBUG:
            values_str = "\n".join(
                [
                    f"{key}: {str_or_none(value)}"
                    for key, value in values.items()
                    if key != "-OUTPUT-"
                ]
            )
            listbox_selected_items_str = "\n".join(settings["slots_to_upload"])

            window["-OUTPUT-"].update(
                f"Last event: {event}\n"
                f"-----------\n"
                f"Values:\n"
                f"-------\n"
                f"{values_str}"
                f"\nListbox values:\n"
                f"{listbox_selected_items_str}"
            )

    window.close()
