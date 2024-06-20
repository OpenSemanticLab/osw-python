from osw.utils.strings import RegExPatternExtended

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
    RegExPatternExtended(
        description="File page strings from any text",
        pattern=r"(File:(OSW[0-9a-fA-F]{32})((?:\.[\w-]+)*))",
        group_keys=["Full page name", "OSW-ID", "Suffix(es)"],
        example_str="File:OSWb701155d41ad44ab9ad719edc3a2480a.drawio.png",
        expected_groups=[
            "File:OSWb701155d41ad44ab9ad719edc3a2480a.drawio.png",
            "OSWb701155d41ad44ab9ad719edc3a2480a",
            ".drawio.png",
        ],
    ),
    RegExPatternExtended(
        description="SAP OU number and name from DN",
        pattern=r"CN=(.+)([0-9]{10})-(.+),OU=Abteilungen",
        group_keys=["Something", "SAP OU number", "SAP OU name"],
    ),
    RegExPatternExtended(
        description="Location name from DN",
        pattern=r"CN=[A-Za-z]+\-(\d+)_L_([^_]+),OU=Standorte",
        group_keys=["SAP institute number", "Location name"],
    ),
    RegExPatternExtended(
        description="Location/Site parts from DN",
        pattern=r"CN=[A-Za-z]+\-(\d+)_L_(([^_^ ^-]+)-([^_^ ]+) (\d+))," r"OU=Standorte",
        group_keys=[
            "SAP institute number",
            "Site name",
            "City",
            "Street",
            "House number",
        ],
    ),
    RegExPatternExtended(
        description="UUID from full page title",
        pattern=r"([A-Za-z]+):([A-Z]+)([a-z\d\-]+)",
        group_keys=["Namespace", "Prefix", "UUID"],
    ),
    RegExPatternExtended(
        description="UUID from OSW ID",
        pattern=r"([A-Z]+)([a-z\d\-]+)",
        group_keys=["Prefix", "UUID"],
    ),
]
REGEX_PATTERN = {rep.description: rep.dict() for rep in REGEX_PATTERN_LIST}
REGEX_PATTERN_LIB = {rep.description: rep for rep in REGEX_PATTERN_LIST}
