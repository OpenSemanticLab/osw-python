"""This script provides a GUI for downloading an OSW instances page slots, editing
them locally and uploading them again."""

import json
import os
from itertools import compress
from pathlib import Path
from typing import List, Optional, Union
from warnings import warn

import mwclient.errors
import PySimpleGUI as psg
import yaml
from numpy import array as np_array

import osw.model.page_package as package
from osw.auth import CredentialManager
from osw.express import OswExpress
from osw.model.static import OswBaseModel
from osw.wiki_tools import read_domains_from_credentials_file
from osw.wtsite import SLOTS, WtPage, WtSite

# Definition of constants
GUI_THEME = "reddit"
DEBUG_DEFAULT = True  # Set to True to get an output element in the GUI
DUMP_EMPTY_SLOTS_DEFAULT = True
SEL_INDICES_DEFAULT = [
    0,  # "main",
    3,  # "jsondata",
    4,  # "jsonschema",
    6,  # "header_template",
]
DOMAIN_DEFAULT = "wiki-dev.open-semantic-lab.org"
SLOTS_TO_UPLOAD_DEFAULT = np_array(list(SLOTS.keys()))[SEL_INDICES_DEFAULT].tolist()
TARGET_PAGE_DEFAULT = "Main_Page"
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


# Definition of classes
class Settings(OswBaseModel):
    credentials_file_path: Optional[Union[str, Path]] = CREDENTIALS_FILE_PATH_DEFAULT
    local_working_directory: Optional[Union[str, Path]] = LWD_DEFAULT
    settings_file_path: Optional[Union[str, Path]] = SETTINGS_FILE_PATH_DEFAULT
    target_pages: Optional[List[str]] = [TARGET_PAGE_DEFAULT]
    namespace_as_folder: Optional[bool] = NAMESPACE_AS_FOLDER
    dump_empty_slots: Optional[bool] = DUMP_EMPTY_SLOTS_DEFAULT
    debug: Optional[bool] = DEBUG_DEFAULT
    page_name_as_filename: Optional[bool] = True
    slots_to_upload: Optional[list] = SLOTS_TO_UPLOAD_DEFAULT
    download_first: Optional[bool] = True
    """Whether the slots of a page have to be downloaded in the same session of the
    GUI before they can be uploaded. If set to False, the slots can be uploaded
    without downloading them first."""
    domain: Optional[str] = DOMAIN_DEFAULT

    def create_config(self) -> WtPage.PageDumpConfig:
        config_ = WtPage.PageDumpConfig(
            target_dir=self.local_working_directory,
            namespace_as_folder=self.namespace_as_folder,
            dump_empty_slots=self.dump_empty_slots,
            page_name_as_filename=self.page_name_as_filename,
        )
        return config_


class SinglePageInteraction:
    def __init__(self, target_page: str, wtsite_inst: WtSite, settings_inst: Settings):
        self.url_or_fpn = target_page
        self.wtsite: WtSite = wtsite_inst
        self.settings: Settings = settings_inst
        self.label_set: Optional[bool] = False
        self.label: Optional[str] = None
        self.slots_downloaded: Optional[bool] = False
        self.full_page_name = get_fpn_from_url(target_page)
        self.url = get_url_from_fpn_and_domain(
            self.full_page_name, self.settings.domain
        )
        self.page_package_bundle: package.PagePackageBundle = None
        self.page_package_config: package.PagePackageConfig = None
        # Call functions
        self.create_bundle_and_config()

    def create_bundle_and_config(
        self,
        dump_config_inst: WtPage.PageDumpConfig = None,
        top_level: str = None,
        sub_level: str = None,  # "content"
        author: Union[str, list] = "Open Semantic World",
    ):
        if dump_config_inst is None:
            dump_config_inst = self.settings.create_config()
        if top_level is None:
            top_level = self.full_page_name.split(":")[-1]
        package_repo_org = "OpenSemanticWorld-Packages"
        package_repo = f"{top_level}.{sub_level}"
        package_id = f"{top_level}.{sub_level}"
        package_name = top_level
        package_subdir = sub_level
        package_branch = "deleteme"
        publisher = "Open Semantic World"
        working_dir = dump_config_inst.target_dir
        label_str = self.label
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
        self.page_package_bundle = package.PagePackageBundle(
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
        self.page_package_config = package.PagePackageConfig(
            name=package_name,
            config_path=os.path.join(target_dir, PACKAGE_INFO_FILE_NAME),
            content_path=content_path,
            bundle=self.page_package_bundle,
            titles=[self.full_page_name],
        )

    def save_as_page_package(
        self,
        dump_config_inst: WtPage.PageDumpConfig,
        top_level: str = None,
        sub_level: str = None,  # "content"
        author: Union[str, list] = "Open Semantic World",
    ):
        self.create_bundle_and_config(
            dump_config_inst=dump_config_inst,
            top_level=top_level,
            sub_level=sub_level,
            author=author,
        )
        self.wtsite.create_page_package(
            WtSite.CreatePagePackageParam(
                config=self.page_package_config,
                dump_config=dump_config_inst,
                debug=False,
            )
        )
        return {
            "Page package bundle": self.page_package_bundle,
            "Page package config": self.page_package_config,
        }


# Definition of functions
def get_fpn_from_url(url) -> str:
    first_split = url.split("?")[0]
    return first_split.split("/")[-1]


def get_url_from_fpn_and_domain(fpn: str, domain: str) -> str:
    return f"https://{domain}/wiki/{fpn}"


def str_or_none(value):
    if str(value) == "" or value is None:
        return str("None")
    else:
        return str(value)


def single_page_helper(
    item_num: int, fpn: str, settings_inst: Settings, wtsite_inst: WtSite
):
    # fpt = ""
    # if item_num < len(settings_inst.target_pages):
    spi = SinglePageInteraction(
        target_page=fpn, wtsite_inst=wtsite_inst, settings_inst=settings_inst
    )
    row = [
        # Single target page
        psg.pin(
            psg.Col(
                [
                    [
                        psg.Text(f"#{item_num}", k=("-STATUS-", item_num)),
                        psg.Input(
                            size=(45, 1),
                            default_text=fpn,
                            k=("-ADDRESS-", item_num),
                            tooltip="Address, within selected OSW instance",
                            enable_events=True,
                        ),
                        psg.Button("Load", k=("-LOAD-", item_num)),
                        psg.Multiline(
                            size=(30, 1),
                            key=("-LABEL-", item_num),
                            no_scrollbar=True,
                            tooltip="First label of the selected OSW page",
                        ),
                        psg.Button(
                            "DL",
                            k=("-DL-", item_num),
                            tooltip="Download selected slots",
                        ),
                        psg.Button(
                            "FE",
                            k=("-OL-", item_num),
                            tooltip="Open the local folder with the downloaded slots "
                            "in File Explorer",
                        ),
                        psg.Button(
                            "VSC",
                            k=("-VSC-", item_num),
                            tooltip="Open the local folder with the downloaded slots "
                            "in Visual Studio Code",
                        ),
                        psg.Button(
                            "UL", k=("-UL-", item_num), tooltip="Upload selected slots"
                        ),
                        psg.Multiline(
                            size=(20, 1),
                            key=("-RES-", item_num),
                            no_scrollbar=True,
                            tooltip="Result of 'Load', 'Download' or 'Upload'",
                        ),
                        psg.Button(
                            "OP",
                            k=("-OP-", item_num),
                            tooltip="Open the page in the browser",
                        ),
                        psg.Button(
                            "X",
                            # border_width=0,
                            # button_color=(psg.theme_text_color(),
                            #               psg.theme_background_color()),
                            k=("-DEL-", item_num),
                            tooltip="Remove this item",
                        ),
                    ]
                ],
                k=("-ROW-", item_num),
            )
        ),
    ]

    return row, spi


def make_window(
    settings_inst: Settings,
    wtsite_inst: WtSite,
    domains: List[str],
    domain: str,
):
    # ----- GUI Definition -----
    # Setting the theme of the GUI
    psg.theme(GUI_THEME)
    # Settings
    settings_layout = [
        [psg.Text("Settings", font=("Helvetica", 20))],
        [psg.Text("General", font=("Helvetica", 16))],
        [
            # 1 Labels
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
            # 2 Input fields / Browse buttons
            psg.Column(
                [
                    [
                        psg.In(
                            size=(50, 1),
                            enable_events=True,
                            key="-SETTINGS-",
                            default_text=settings_inst.settings_file_path,
                        ),
                        psg.FileBrowse(
                            button_text="Browse",
                            key="-BROWSE_SETTINGS-",
                            tooltip="Select a settings file",
                        ),
                    ],
                    [
                        psg.In(
                            size=(50, 1),
                            enable_events=True,
                            key="-CREDENTIALS-",
                            default_text=settings_inst.credentials_file_path,
                        ),
                        psg.FileBrowse(
                            button_text="Browse",
                            key="-BROWSE_CREDENTIALS-",
                            tooltip="Select a credentials file",
                        ),
                    ],
                    [
                        psg.In(
                            size=(50, 1),
                            enable_events=True,
                            key="-LWD-",
                            default_text=settings_inst.local_working_directory,
                        ),
                        psg.FolderBrowse(
                            button_text="Browse",
                            key="-BROWSE_LWD-",
                            tooltip="Select a local working directory",
                        ),
                    ],
                ]
            ),
            # 3 Load / Open buttons
            psg.Column(
                [
                    [
                        psg.Button(
                            button_text="Load",
                            key="-LOAD_SETTINGS-",
                            tooltip="Load settings from file. Will restart the GUI!\n"
                            "Maintains the current session.",
                        ),
                    ],
                    [
                        psg.Button(
                            button_text="Open",
                            key="-OPEN_CREDENTIALS-",
                        ),
                    ],
                    [
                        psg.Button(
                            button_text="Open",
                            key="-OPEN_LWD-",
                        ),
                    ],
                ]
            ),
            # 4 Save / VSC buttons
            psg.Column(
                [
                    [
                        psg.Button(
                            button_text="Save",
                            key="-SAVE_SETTINGS-",
                            tooltip="Save settings to the specified path",
                        ),
                    ],
                    [
                        psg.Button(
                            "VSC",
                            k="-VSC_CREDENTIALS-",
                            tooltip="Opens the credential file in Visual Studio Code",
                        ),
                    ],
                    [
                        psg.Button(
                            "VSC",
                            k="-VSC_LWD-",
                            tooltip="Opens the local working directory in Visual "
                            "Studio Code",
                        ),
                    ],
                ]
            ),
        ],
        # Debugging settings
        [psg.Text("Debugging", font=("Helvetica", 16))],
        [
            psg.Column(
                [
                    [
                        psg.Radio(
                            "Show debug output",
                            group_id="-RADIO2-",
                            default=settings_inst.debug,
                            key="-SHOW_DEBUG-",
                            enable_events=True,
                        )
                    ],
                    [
                        psg.Radio(
                            "Hide debug output",
                            group_id="-RADIO2-",
                            default=(not settings_inst.debug),
                            key="-HIDE_DEBUG-",
                            enable_events=True,
                        )
                    ],
                ]
            ),
            psg.Column(
                [
                    [
                        psg.Button(
                            button_text="Restart to apply",
                            key="-RESTART-",
                            tooltip="Restarts the GUI with the current settings and "
                            "maintains\n"
                            "the current session.",
                        ),
                    ]
                ]
            ),
        ],
        # Slot settings
        [
            psg.Text(
                "Slots",
                font=("Helvetica", 16),
                tooltip="The slots of a page are the different parts of the page that\n"
                "can be edited. They are stored as JSON or wikitext files in \n"
                "the page package.",
            )
        ],
        [
            psg.Column(
                [
                    # Slots to download
                    [
                        psg.Text(
                            "Slots to download",
                            font=("Helvetica", 12),
                            tooltip="Choose 'Include empty slots' to download all slots\n"
                            "of a page\n, e.g., when you want to fill a slot for\n"
                            "the first time. Choose 'Exclude empty slots to'\n"
                            "download only the slots that have content.",
                        )
                    ],
                    [
                        psg.Radio(
                            "Include empty slots",
                            group_id="-RADIO1-",
                            default=settings_inst.dump_empty_slots,
                            key="-INC_EMPTY-",
                            enable_events=True,
                            tooltip="Hover over 'Slots to download' for more "
                            "information.",
                        )
                    ],
                    [
                        psg.Radio(
                            "Exclude empty slots",
                            group_id="-RADIO1-",
                            default=(not settings_inst.dump_empty_slots),
                            key="-EXC_EMPTY-",
                            enable_events=True,
                            tooltip="Hover over 'Slots to download' for more "
                            "information.",
                        )
                    ],
                    [psg.Text()],
                    # Slots: download first?
                    [
                        psg.Text(
                            "Force remote",
                            font=("Helvetica", 12),
                            tooltip="This setting determines whether the slots of a page have to\n"
                            "be downloaded in the same session of the GUI before they can\n"
                            "be uploaded. If set to 'Download remote slots first', the\n"
                            "slots can be uploaded without downloading them first.",
                        )
                    ],
                    [
                        psg.Radio(
                            "Download remote slots first",
                            group_id="-RADIO3-",
                            default=settings_inst.download_first,
                            key="-DL_FIRST-",
                            enable_events=True,
                            tooltip="Hover over 'Force remote' for more information.",
                        )
                    ],
                    [
                        psg.Radio(
                            "Upload local slots directly",
                            group_id="-RADIO3-",
                            default=(not settings_inst.download_first),
                            key="-UL_DIRECTLY-",
                            enable_events=True,
                            tooltip="Hover over 'Force remote' for more information.",
                        )
                    ],
                ]
            ),
            # Slots to upload
            psg.Column(
                [
                    [psg.Text("Slots to upload", font=("Helvetica", 12))],
                    [
                        psg.Listbox(
                            values=SLOTS.keys(),
                            default_values=settings_inst.slots_to_upload,
                            size=(20, 10),
                            key="-UL_LIST-",
                            select_mode=psg.LISTBOX_SELECT_MODE_MULTIPLE,
                            enable_events=True,
                            no_scrollbar=True,
                        )
                    ],
                    [
                        psg.Column([[psg.Button("(De)Select all", key="-UL_SEL-")]]),
                        psg.Column([[psg.Button("Default", key="-UL_SEL_DEF-")]]),
                    ],
                ]
            ),
        ],
        [psg.HSeparator()],
    ]
    # Prepare the rows for single page interaction objects (saved in settings)
    res = [
        single_page_helper(
            ii, settings_inst.target_pages[ii], settings_inst, wtsite_inst  # fpn
        )
        for ii in range(len(settings_inst.target_pages))
    ]
    rows = [item[0] for item in res]
    spi_objects = [item[1] for item in res]
    # Actions
    actions_layout = [
        # Actions
        [psg.Text("Actions", font=("Helvetica", 20))],
        # Target OSW instance
        [psg.Text("Target OSW instance", font=("Helvetica", 16))],
        [
            psg.Text(
                "List of domains is read from accounts.pwd.yaml!",
                tooltip=f"To add more domains, modify accounts.pwd.yaml, located here:\n"
                f"{Path(settings_inst.credentials_file_path).parent}",
            )
        ],
        [
            psg.Combo(
                domains, default_value=domain, key="-DOMAIN-", enable_events=True
            ),
            psg.Button(
                "Add new domain",
                key="-ADD_DOMAIN-",
                tooltip="Will test the credentials and restart with the new domain\n "
                "selected, if credentials are correct. Otherwise will "
                "prompt the user to try again.\n"
                "A domain can only be listed once. If you add "
                "credentials for\n"
                "an already existing domain, previous credentials are\n"
                "overwritten.",
            ),
        ],
        # List of target pages
        [psg.Text("Target pages", font=("Helvetica", 16))],
        [
            psg.Text(
                "Hints - Hover over me",
                tooltip="1. Add and 'remove' (make them invisible) rows.\n"
                "2. The 'Load' button will load the label of the page \n"
                "3. The 'DL' (Download) button will download the slots of the \n"
                "page. \n"
                "4. The 'OL' (Open local) button will open the local folder with \n"
                "the downloaded slots in the file explorer. Slots need to be \n"
                "downloaded first. \n"
                "5. The 'UL' (Upload) button will upload the slots of the page \n"
                "from the local folder to the selected OSW instance. \n"
                "The upload will fail and 'Error: JSON Decode Error' will be \n"
                "displayed next to the 'UL' button if the one of the JSON files \n"
                "associated with the page to be uploaded contains an error. \n"
                "6. The 'OP' (Open page) button will open the page in the\n"
                "browser.\n"
                "7. The 'X' button will remove (set to invisible) the row next\n"
                "to it",
            )
        ],
        [
            psg.Button(
                "Load all",
                key="-LOAD_ALL-",
                tooltip="Load listed pages and display their labels (serially)",
            ),
            psg.Button(
                "Download all",
                key="-DL_ALL-",
                tooltip="Download listed pages (serially). Press 'Load all' first!",
            ),
            psg.Button(
                "Upload all", key="-UL_ALL-", tooltip="Upload listed pages (serially)"
            ),
            psg.Button(
                "Remove all",
                key="-DEL_ALL-",
                tooltip="Remove listed pages from the list (make them invisible)",
            ),
        ],
        [psg.Text()],
        [psg.Col(rows, k="-PAGE INTERACTION-")],
        [
            psg.Button(
                "Add row", enable_events=True, k="Add Item", tooltip="Add Another Item"
            ),
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
    if settings_inst.debug:
        layout += output_layout
    # Create the window
    window = psg.Window(
        "OSW local editing GUI",
        layout,
        use_default_focus=True,
        metadata=len(spi_objects) - 1,
        finalize=True,
    )

    return window, spi_objects


def main():
    # Predefining some variables before execution
    settings_file_path = SETTINGS_FILE_PATH_DEFAULT
    if os.path.exists(settings_file_path):
        with open(settings_file_path, "r") as f:
            settings_dict = json.load(f)
            settings = Settings(**settings_dict)
        settings_read_from_file = True
    else:
        settings = Settings()
        settings_read_from_file = False

    domains, accounts = read_domains_from_credentials_file(
        settings.credentials_file_path
    )
    if "wiki-dev.open-semantic-lab.org" in domains:
        domain = DOMAIN_DEFAULT
    else:
        domain = domains[0]
    if settings_read_from_file:
        settings.domain = domain
    if not os.path.exists(settings_file_path):
        # Make sure the settings file is created with the default values if it does not
        # exist
        with open(settings_file_path, "w") as f:
            json.dump(
                settings.dict(),
                f,
                indent=4,
                default=lambda x: str(x),
                ensure_ascii=False,
            )
    try:
        cm = CredentialManager(cred_filepath=settings.credentials_file_path)
        osw_obj = OswExpress(domain=domain, cred_mngr=cm)
    except mwclient.errors.LoginError:
        # Write a simple pysimplegui popup window to enter username and password for
        # the selected domain
        layout = [
            [
                psg.Text(
                    "Please enter username and password for the domain:\n"
                    f"{domain}\n",
                    font=("Helvetica", 12),
                )
            ],
            [
                psg.Text(
                    "The usage of a bot passwords is preferred over personal\n"
                    "passwords!"
                )
            ],
            [
                psg.Text(
                    "The credentials will be saved in the credentials file, "
                    "located at:\n."
                    f"{settings.credentials_file_path}"
                )
            ],
            [
                psg.Column([[psg.Text("Username")], [psg.Text("Password")]]),
                psg.Column(
                    [
                        [psg.InputText(key="-USERNAME-")],
                        [psg.InputText(key="-PASSWORD-", password_char="*")],
                    ]
                ),
            ],
            [psg.Button("OK"), psg.Button("Cancel")],
        ]
        window = psg.Window("Enter credentials", layout)
        event, values = window.read()
        window.close()
        if event == "Cancel" or event == psg.WIN_CLOSED:
            return
        username = values["-USERNAME-"]
        password = values["-PASSWORD-"]
        accounts[domain] = {"username": username, "password": password}
        with open(settings.credentials_file_path, "w") as f:
            yaml.dump(accounts, f)
        # try again
        cm = CredentialManager(cred_filepath=settings.credentials_file_path)
        osw_obj = OSW(site=WtSite(WtSite.WtSiteConfig(iri=domain, cred_mngr=cm)))

    wtsite_obj = osw_obj.site

    window, spi_objects = make_window(
        settings_inst=settings,
        wtsite_inst=wtsite_obj,
        domains=domains,
        domain=domain,
    )
    active_rows = [True] * len(spi_objects)

    # Create an event loop
    while True:
        event, values = window.read()
        # End program if user closes window or
        # presses the OK button
        if event == "OK" or event == psg.WIN_CLOSED:
            break
        if event == "Add Item":
            window.metadata += 1
            if len(settings.target_pages) < window.metadata + 1:
                settings.target_pages.append("")
            fpn = get_fpn_from_url(settings.target_pages[window.metadata])
            row, spi = single_page_helper(window.metadata, fpn, settings, wtsite_obj)
            window.extend_layout(window["-PAGE INTERACTION-"], [row])
            spi_objects.append(spi)
            active_rows.append(True)
        elif event == "-SETTINGS-":
            settings.settings_file_path = values["-SETTINGS-"]
        elif event == "-RESTART-":
            window.close()
            window, spi_objects = make_window(
                settings_inst=settings,
                wtsite_inst=wtsite_obj,
                domains=domains,
                domain=domain,
            )
        elif event == "-LOAD_SETTINGS-":
            # update settings
            with open(settings.settings_file_path, "r") as f:
                settings_dict = json.load(f)
                settings = Settings(**settings_dict)
            window.close()
            window, spi_objects = make_window(
                settings_inst=settings,
                wtsite_inst=wtsite_obj,
                domains=domains,
                domain=domain,
            )
            active_rows = [True] * len(spi_objects)
            """
            # update GUI
            window["-CREDENTIALS-"].update(settings.credentials_file_path),
            window["-LWD-"].update(settings.local_working_directory)
            window["-DOMAIN-"].update(settings.domain)
            window["-INC_EMPTY-"].update(settings.dump_empty_slots)
            window["-EXC_EMPTY-"].update(not settings.dump_empty_slots)
            indices = [
                i
                for i, x in enumerate(SLOTS.keys())
                if x in settings.slots_to_upload
            ]
            window["-UL_LIST-"].update(set_to_index=indices)
            # three cases:
            # number of rows in settings is equal to number of rows in GUI
            # number of rows in settings is less than number of rows in GUI
            # number of rows in settings is greater than number of rows in GUI

            # Set all rows to invisible (valid action for all cases)
            for ii in range(window.metadata):
                window[("-ROW-", ii)].update(visible=False)
                active_rows[ii] = False
            # Create new rows from the settings
            for ii in range(len(settings.target_pages)):
                window.metadata += 1
                fpn = settings.target_pages[ii]
                row, _ = single_page_helper(
                    ii + window.metadata - 1,
                    fpn,
                    settings,
                    wtsite_obj
                )
                spi_object = SinglePageInteraction(
                    target_page=fpn,
                    wtsite_inst=wtsite_obj,
                    settings_inst=settings
                )
                spi_objects.append(
                    spi_object
                )

                window.extend_layout(
                    window["-PAGE INTERACTION-"],
                    [row]
                )
                active_rows.append(True)
            """
            settings_read_from_file = True
        elif event == "-SAVE_SETTINGS-":
            settings.domain = domain
            settings_as_dict = settings.dict()
            # print("Current settings:")
            # print(settings.target_pages)
            settings_as_dict["target_pages"] = list(
                compress(
                    [spi_object.full_page_name for spi_object in spi_objects],
                    active_rows,
                )
            )
            # print("Saved settings:")
            # print(settings_as_dict["target_pages"])
            with open(settings.settings_file_path, "w") as f:
                json.dump(settings_as_dict, f, indent=4, default=lambda x: str(x))
        elif event == "-CREDENTIALS-":
            settings.credentials_file_path = values["-CREDENTIALS-"]
            domains, accounts = read_domains_from_credentials_file(
                settings.credentials_file_path
            )
            window["-DOMAIN-"].update(values=domains)
        elif event == "-LWD-":
            settings.local_working_directory = values["-LWD-"]
        elif event == "-DOMAIN-":
            new_domain = values["-DOMAIN-"].split("//")[-1]
            settings.domain = new_domain
            domain = new_domain

            try:
                osw_obj = OswExpress(domain=settings.domain, cred_mngr=cm)
                wtsite_obj = osw_obj.site
            except mwclient.errors.LoginError:
                # Create a simple warning popup that tells the user to try again
                layout_domain_error = [
                    [
                        psg.Text(
                            "Login Error: Incorrect username or password entered.\n"
                            "Please try again or cancel."
                        )
                    ],
                    [
                        psg.Button("OK", key="OK"),
                        psg.Button("Remove domain", key="Remove"),
                        psg.Button("Cancel", key="Cancel"),
                    ],
                ]
                window_domain_error = psg.Window("Login Error", layout_domain_error)
                event_domain_err, values_domain_err = window_domain_error.read()
                window_domain_error.close()
                if event_domain_err == "Cancel" or event_domain_err == psg.WIN_CLOSED:
                    continue
                elif event_domain_err == "Remove":
                    accounts.pop(new_domain)
                    with open(settings.credentials_file_path, "w") as f:
                        yaml.dump(accounts, f)
                else:
                    window.write_event_value("-ADD_DOMAIN-", new_domain)

        elif event == "-ADD_DOMAIN-":
            domain_default_text = ""
            if "-ADD_DOMAIN-" in values:
                if values["-ADD_DOMAIN-"] is not None:
                    domain_default_text = values["-ADD_DOMAIN-"]
            # write a simple popup window to enter a new domain, username and password
            layout_domain = [
                [
                    psg.Text(
                        "Please enter a new domain, username and password:\n",
                        font=("Helvetica", 12),
                    )
                ],
                [
                    psg.Text(
                        "The usage of a bot passwords is preferred over personal\n"
                        "passwords!"
                    )
                ],
                [
                    psg.Column(
                        [
                            [psg.Text("Domain")],
                            [psg.Text("Username")],
                            [
                                psg.Text("Password"),
                            ],
                        ]
                    ),
                    psg.Column(
                        [
                            [
                                psg.InputText(
                                    key="-NEW_DOMAIN-", default_text=domain_default_text
                                )
                            ],
                            [psg.InputText(key="-NEW_USERNAME-", default_text="")],
                            [psg.InputText(key="-NEW_PASSWORD-", password_char="*")],
                        ]
                    ),
                ],
                [psg.Button("OK"), psg.Button("Cancel")],
            ]
            window_domain = psg.Window(
                "Enter new domain and credentials", layout_domain
            )
            event_domain, values_domain = window_domain.read()
            window_domain.close()
            if event_domain == "Cancel" or event_domain == psg.WIN_CLOSED:
                continue
            new_domain = values_domain["-NEW_DOMAIN-"].split("//")[-1]
            new_username = values_domain["-NEW_USERNAME-"]
            new_password = values_domain["-NEW_PASSWORD-"]
            if new_domain in domains:
                window_warning = psg.Window(
                    "Warning",
                    layout=[
                        [psg.Text("Domain already exists. Overwrite?")],
                        [psg.Button("OK"), psg.Button("Cancel")],
                    ],
                )
                event_warning, _ = window_warning.read()
                window_warning.close()
                if event_warning == "Cancel" or event_warning == psg.WIN_CLOSED:
                    continue
            accounts[new_domain] = {"username": new_username, "password": new_password}
            with open(settings.credentials_file_path, "w") as f:
                yaml.dump(accounts, f)
            domain = new_domain
            settings.domain = new_domain
            cm = CredentialManager(cred_filepath=settings.credentials_file_path)
            try:
                osw_obj = OSW(
                    site=WtSite(WtSite.WtSiteConfig(iri=settings.domain, cred_mngr=cm))
                )
                wtsite_obj = osw_obj.site
                window.write_event_value("-RESTART-", None)
                window.write_event_value("-DOMAIN-", new_domain)
            except mwclient.errors.LoginError:
                # Create a simple warning popup that tells the user to try again
                layout_domain_error = [
                    [
                        psg.Text(
                            "Login Error: Incorrect username or password entered.\n"
                            "Please try again or cancel."
                        )
                    ],
                    [
                        psg.Button("OK", key="OK"),
                        psg.Button("Remove domain", key="Remove"),
                        psg.Button("Cancel", key="Cancel"),
                    ],
                ]
                window_domain_error = psg.Window("Login Error", layout_domain_error)
                event_domain_err, values_domain_err = window_domain_error.read()
                window_domain_error.close()
                if event_domain_err == "Cancel" or event_domain_err == psg.WIN_CLOSED:
                    continue
                elif event_domain_err == "Remove":
                    accounts.pop(new_domain)
                    with open(settings.credentials_file_path, "w") as f:
                        yaml.dump(accounts, f)
                else:
                    window.write_event_value("-ADD_DOMAIN-", None)
        elif event == "-SHOW_DEBUG-" or event == "-HIDE_DEBUG-":
            settings.debug = values["-SHOW_DEBUG-"]
        elif event == "-EXC_EMPTY-" or event == "-INC_EMPTY-":
            settings.dump_empty_slots = values["-INC_EMPTY-"]
        elif event == "-DL_FIRST-" or event == "-UL_DIRECTLY-":
            settings.download_first = values["-DL_FIRST-"]
        elif event == "-UL_SEL-":
            indices = list(window["-UL_LIST-"].get_indexes())
            # All selected: deselect all
            if indices == list(range(len(SLOTS.keys()))):
                window["-UL_LIST-"].update(set_to_index=[])
                settings.slots_to_upload = []
            else:
                window["-UL_LIST-"].update(set_to_index=list(range(len(SLOTS.keys()))))
                settings.slots_to_upload = list(SLOTS.keys())
        elif event == "-UL_SEL_DEF-":
            window["-UL_LIST-"].update(set_to_index=SEL_INDICES_DEFAULT)
            settings.slots_to_upload = SLOTS_TO_UPLOAD_DEFAULT
        elif event == "-UL_LIST-":
            indices = list(window["-UL_LIST-"].get_indexes())
            settings.slots_to_upload = np_array(list(SLOTS.keys()))[indices].tolist()
        elif event == "-LOAD_ALL-":
            # todo: fix - dont try to load elements that are have no address
            for ii in range(len(spi_objects)):
                if active_rows[ii] and values[("-ADDRESS-", ii)] != "":
                    window.write_event_value(("-LOAD-", ii), None)
        elif event == "-DL_ALL-":
            for ii in range(len(spi_objects)):
                if active_rows[ii] and values[("-ADDRESS-", ii)] != "":
                    window.write_event_value(("-DL-", ii), None)
        elif event == "-UL_ALL-":
            for ii in range(len(spi_objects)):
                if active_rows[ii] and values[("-ADDRESS-", ii)] != "":
                    window.write_event_value(("-UL-", ii), None)
        elif event == "-DEL_ALL-":
            for ii in range(len(spi_objects)):
                if active_rows[ii]:
                    window.write_event_value(("-DEL-", ii), None)
        elif event == "-OPEN_CREDENTIALS-":
            os.system(f"start {settings.credentials_file_path}")
        elif event == "-OPEN_LWD-":
            os.system(f"explorer {settings.local_working_directory}")
        elif event == "-VSC_CREDENTIALS-":
            os.system(f'code "{settings.credentials_file_path}"')
        elif event == "-VSC_LWD-":
            os.system(f'code "{settings.local_working_directory}"')
        elif event[0] == "-ADDRESS-":
            address = values[("-ADDRESS-", event[1])]
            fpn = get_fpn_from_url(address)
            # print(f"Address: {address}, FPN: {fpn}")
            settings.target_pages[event[1]] = fpn
            spi_objects[event[1]].full_page_name = fpn
            spi_objects[event[1]].url = get_url_from_fpn_and_domain(
                fpn, settings.domain
            )
            window[("-ADDRESS-", event[1])].update(fpn)
            window[("-LABEL-", event[1])].update("")
            window[("-RES-", event[1])].update("")
        elif event[0] == "-DEL-":
            window[("-ROW-", event[1])].update(visible=False)
            active_rows[event[1]] = False
        elif event[0] == "-LOAD-":
            window[("-LABEL-", event[1])].update("Loading page...")
            window[("-RES-", event[1])].update("")
            full_page_name = (
                values[("-ADDRESS-", event[1])].split("/")[-1].replace("_", " ")
            )
            if (values[("-ADDRESS-", event[1])].find("/wiki/") != -1) or (
                values[("-ADDRESS-", event[1])].find("/w/") != -1
            ):
                if len(settings.target_pages) < event[1] + 1:
                    settings.target_pages.append(values[("-ADDRESS-", event[1])])
                else:
                    settings.target_pages[event[1]] = values[("-ADDRESS-", event[1])]
            else:
                if len(settings.target_pages) < event[1] + 1:
                    settings.target_pages.append(
                        get_url_from_fpn_and_domain(full_page_name, domain)
                    )
                else:
                    settings.target_pages[event[1]] = get_url_from_fpn_and_domain(
                        full_page_name, domain
                    )
            # if values[("-ADDRESS-", event[1])].find(settings.domain) == -1:
            #     window[("-LABEL-", event[1])].update("Page not on selected domain!")
            #     spi_objects[event[1]].label_set = False
            # else:
            # use connection
            page = wtsite_obj.get_page(
                WtSite.GetPageParam(titles=[full_page_name])
            ).pages[0]
            if page.exists:
                jsondata = page.get_slot_content("jsondata")
                if jsondata is None:
                    window[("-LABEL-", event[1])].update("Slot 'jsondata' is empty!")
                    spi_objects[event[1]].label_set = False
                else:
                    label = jsondata["label"][0]["text"]
                    spi_objects[event[1]].label = label
                    window[("-LABEL-", event[1])].update(label)
                    spi_objects[event[1]].label_set = True
            else:
                window[("-LABEL-", event[1])].update("Page does not exist!")
                spi_objects[event[1]].label_set = False
            window[("-RES-", event[1])].update("Labeled")
        elif event[0] == "-DL-":
            window[("-RES-", event[1])].update("Downloading")
            if not spi_objects[event[1]].label_set:
                window.write_event_value(("-LOAD-", event[1]), None)
            dump_config = settings.create_config()
            _ = spi_objects[event[1]].save_as_page_package(
                dump_config_inst=dump_config,
                sub_level=SUB_LEVEL,
                author=accounts[domain]["username"],
            )
            spi_objects[event[1]].slots_downloaded = True
            window[("-RES-", event[1])].update("Downloaded!")
        elif event[0] == "-OL-":
            if not spi_objects[event[1]].slots_downloaded:
                # window.write_event_value(("-DL-", event[1]), None)
                spi_objects[event[1]].create_bundle_and_config()
            if not spi_objects[event[1]].label_set:
                window.write_event_value(("-LOAD-", event[1]), None)
            storage_path = Path(spi_objects[event[1]].page_package_config.content_path)
            # print(storage_path)
            if storage_path.exists():
                os.system(f"explorer {storage_path}")
            else:
                window[("-RES-", event[1])].update("Error: Folder not found!")
        elif event[0] == "-VSC-":
            if not spi_objects[event[1]].slots_downloaded:
                # window.write_event_value(("-DL-", event[1]), None)
                spi_objects[event[1]].create_bundle_and_config()
            if not spi_objects[event[1]].label_set:
                window.write_event_value(("-LOAD-", event[1]), None)
            storage_path = Path(spi_objects[event[1]].page_package_config.content_path)
            # print(storage_path)
            if storage_path.exists():
                os.system(f'code "{storage_path}"')
            else:
                window[("-RES-", event[1])].update("Error: Folder not found!")
        elif event[0] == "-UL-":
            slots_to_upload = settings.slots_to_upload
            if not spi_objects[event[1]].label_set:
                window[("-RES-", event[1])].update("No page loaded!")
                window.write_event_value(("-DL-", event[1]), None)
            elif len(slots_to_upload) == 0:
                window[("-RES-", event[1])].update("No slots selected!")
            else:
                if (
                    not spi_objects[event[1]].slots_downloaded
                    and settings.download_first
                ):
                    window[("-RES-", event[1])].update("No slots downloaded!")
                else:
                    window[("-RES-", event[1])].update("Uploading slots...")
                    storage_path = spi_objects[
                        event[1]
                    ].page_package_config.content_path
                    try:
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
                        window[("-RES-", event[1])].update("Uploaded!")
                    except json.decoder.JSONDecodeError as e:
                        window[("-RES-", event[1])].update("Error: JSON Decode Error")
                        # label = window[("-LABEL-", event[1])].get()
                        label = spi_objects[event[1]].label
                        warn(f"An error occurred during upload of {label}:")
                        warn(f"{e}")
        if event[0] == "-OP-":
            full_page_name = values[("-ADDRESS-", event[1])].split("/")[-1]
            url = get_url_from_fpn_and_domain(full_page_name, domain)
            os.system(f"start {url}")

        # Some debugging output functionality
        if "-OUTPUT-" in window.key_dict and event != "-LOAD_SETTINGS-":
            # if settings.debug and event != "-LOAD_SETTINGS-":
            values_str = "\n".join(
                [
                    f"{key}: {str_or_none(value)}"
                    for key, value in values.items()
                    if key != "-OUTPUT-"
                ]
            )
            listbox_selected_items_str = "\n".join(settings.slots_to_upload)

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


if __name__ == "__main__":
    main()
