"""
# todo: docstring erzeugen

verwende: beispiel create page package
https://github.com/OpenSemanticLab/osw-python/blob/main/examples/create_page_package.py
in wtsite neuen parameter hinzufügen --> label als file name:
dumpy_empty_slots = False
https://github.com/OpenSemanticLab/osw-python/blob/main/src/osw/wtsite.py#L112
"""
import json
import PySimpleGUI as psg
import os
import yaml
from pathlib import Path
from typing import Union
from numpy import array as np_array

from osw.core import OSW
from osw.wtsite import WtPage, WtSite, SLOTS


# Definition of constants
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


# Defintion of functions
def create_config_from_setting(settings_: dict):
    config_ = WtPage.PageDumpConfig(
        target_dir=settings_["local_working_directory"],
        dump_empty_slots=settings_["dump_empty_slots"],
        page_name_as_filename=settings_["page_name_as_filename"]
    )
    return config_


# Predefining some variables before execution
# Create/update the password file under examples/accounts.pwd.yaml
 # pwd_file_path = "./accounts.pwd.yaml"
pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)
with open(pwd_file_path, "r") as stream:
    try:
        accounts = yaml.safe_load(stream)
        for domain in accounts:
            if domain == domain:
                user = accounts[domain]["username"]
                password = accounts[domain]["password"]
    except yaml.YAMLError as exc:
        print(exc)

domains = list(accounts.keys())
if len(domains) == 0:
    raise ValueError("No domain found in accounts.pwd.yaml!")

wtsite_obj = WtSite.from_domain(
    domain=domains[0],
    password_file=pwd_file_path,
    credentials=accounts[domains[0]]

)
osw_obj = OSW(site=wtsite_obj)

settings_file_path = SETTINGS_FILE_PATH_DEFAULT
if os.path.exists(settings_file_path):
    with open(settings_file_path, "r") as f:
        settings = json.load(f)
else:
    settings = {
        "local_working_directory": str(LWD_DEFAULT),
        "settings_file_path": str(SETTINGS_FILE_PATH_DEFAULT),
        "target_page": TARGET_PAGE_DEFAULT,
        "dump_empty_slots": DUMP_EMPTY_SLOTS_DEFAULT,
        "page_name_as_filename": True,
        "slots_to_upload": SLOTS_TO_UPLOAD_DEFAULT,
        "domain": domains[0]
    }
label_set = False

# ----- GUI Definition -----
# Setting the theme of the GUI
psg.theme("reddit")
# Settings
settings_layout = [

    [
        psg.Text("Settings", font=("Helvetica", 20))
    ],
    [
        psg.Column(
            [
                [
                    psg.Text("Settings file"),
                ],
                [
                    psg.Text("Local working directory"),
                ]
            ]
        ),
        psg.Column(
            [
                [
                    psg.In(size=(50, 1), enable_events=True, key="-SETTINGS-",
                           default_text=SETTINGS_FILE_PATH_DEFAULT),
                    psg.FileBrowse(button_text="Browse", key="-BROWSE_SETTINGS-"),
                    psg.Button("Load", key="-LOAD_SETTINGS-"),
                    psg.Button("Save", key="-SAVE_SETTINGS-")
                ],
                [
                    psg.In(size=(50, 1), enable_events=True, key="-LWD-",
                           default_text=LWD_DEFAULT),
                    psg.FolderBrowse(button_text="Browse", key="-BROWSE_LWD-")
                ]
            ]
        )
    ],
    [
        psg.HSeparator()
    ]
]
# Actions
actions_layout = [
    # Actions
    [
        psg.Text("Actions", font=("Helvetica", 20))
    ],
    # Target OSW instace
    [
        psg.Text("Target OSW instance", font=("Helvetica", 16))
    ],
    [
        psg.Text("List of domains is read from accounts.pwd.yaml!")
    ],
    [
        psg.Combo(domains, default_value=domains[0], key='-DOMAIN-',
                  enable_events=True)
    ],
    # Target page
    [
        psg.Text("Target page", font=("Helvetica", 16))
    ],
    [
        psg.Column(
            [
                [
                    psg.Text("Address, within selected OSW instance")
                ],
                [
                    psg.Text("First label of the OSW page:")
                ]
            ]
        ),
        psg.Column(
            [
                [
                    psg.InputText(
                        default_text=TARGET_PAGE_DEFAULT,
                        key="-ADDRESS-"
                    ),
                    psg.Button("Load page")
                ],
                [
                    # A display element that will show the label of the OSW page
                    psg.Text(size=(40, 1), key="-LABEL-")
                ]
            ]
        )
    ],
    # [
    #     psg.HSeparator()
    # ],
    # Slots to download
    [
        psg.Text("Slots to download", font=("Helvetica", 16))
    ],
    [
        psg.Column(
            [
                [
                    psg.Radio("Include empty slots", group_id="-RADIO1-",
                              default=DUMP_EMPTY_SLOTS_DEFAULT, key="-INC_EMPTY-",
                              enable_events=True)
                ],
                [
                    psg.Radio("Exclude empty slots", group_id="-RADIO1-",
                              default=(not DUMP_EMPTY_SLOTS_DEFAULT), key="-EXC_EMPTY-",
                              enable_events=True)
                ],
                [
                    psg.Button("Download selected", key="-DL-")
                ],
            ]
        ),
    ],
    # [
    #     psg.HSeparator()
    # ],
    # Slots to upload
    [
        psg.Text("Slots to upload", font=("Helvetica", 16))
    ],
    [
        psg.Column(
            [
                [
                    psg.Button("(De)Select all", key="-UL_SEL-")
                ],
                [
                    psg.Listbox(
                        values=SLOTS.keys(),
                        default_values=SLOTS_TO_UPLOAD_DEFAULT,
                        size=(20, 10),
                        key="-UL_LIST-",
                        select_mode=psg.LISTBOX_SELECT_MODE_MULTIPLE,
                        enable_events=True,
                        no_scrollbar=True
                    )
                ],
                [
                    psg.Button("Upload selected", key="-UL-")
                ]
            ]
        )
    ],
    [
        psg.HSeparator()
    ],
    # Output
    [
        psg.Text("Debug output", font=("Helvetica", 20))
    ],
    [
        psg.Multiline(key="-OUTPUT-", size=(100, 10))
    ]
]
# The full layout
layout = settings_layout + actions_layout
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
        window["-LWD-"].update(settings["local_working_directory"])
        window["-DOMAIN-"].update(settings["domain"])
        window["-ADDRESS-"].update(settings["target_page"])
        window["-INC_EMPTY-"].update(settings["dump_empty_slots"])
        window["-EXC_EMPTY-"].update(not settings["dump_empty_slots"])
        indices = \
            [i for i, x in enumerate(SLOTS.keys()) if x in settings["slots_to_upload"]]
        window["-UL_LIST-"].update(set_to_index=indices)
    elif event == "-SAVE_SETTINGS-":
        with open(settings["settings_file_path"], "w") as f:
            json.dump(settings, f)
    elif event == "-LWD-":
        settings["local_working_directory"] = values["-LWD-"]
    elif event == "-DOMAIN-":
        settings["domain"] = values["-DOMAIN-"]
        wtsite_obj = WtSite.from_domain(
            domain=settings["domain"],
            password_file="",
            credentials=accounts[settings["domain"]]
        )
        osw_obj = OSW(site=wtsite_obj)
    elif event == "Load page":
        full_page_name = values["-ADDRESS-"].split("/")[-1].replace('_', ' ')
        if (values["-ADDRESS-"].find("/wiki/") != -1) or \
                (values["-ADDRESS-"].find("/w/") != -1):
            settings["target_page"] = values["-ADDRESS-"]
        else:
            settings["target_page"] = "https://" + domain + "/wiki/" + full_page_name
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
        if label_set:
            config = create_config_from_setting(settings)
            page.dump(config)
    elif event == "-UL_SEL-":
        indices = list(window["-UL_LIST-"].get_indexes())
        # All selected: deselect all
        if indices == list(range(len(SLOTS.keys()))):
            window["-UL_LIST-"].update(set_to_index=[])
        else:
            window["-UL_LIST-"].update(set_to_index=list(range(len(SLOTS.keys()))))
    elif event == "-UL_LIST-":
        indices = list(window["-UL_LIST-"].get_indexes())
        settings["slots_to_upload"] = \
            np_array(list(SLOTS.keys()))[indices].tolist()

    def str_or_none(value):
        if str(value) == "" or value is None:
            return str("None")
        else:
            return str(value)

    # Some debugging output functionality
    values_str = "\n".join(
        [f"{key}: {str_or_none(value)}"
         for key, value in values.items() if key != "-OUTPUT-"]
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
