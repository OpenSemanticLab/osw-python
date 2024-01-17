import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Union
from warnings import warn

from pydantic import FilePath
from typing_extensions import Dict, List

import osw.model.page_package as model
from osw.auth import CredentialManager
from osw.data.mining import RegExPatternExtended
from osw.model import page_package as package
from osw.model.page_package import NAMESPACE_CONST_TO_NAMESPACE_MAPPING
from osw.model.static import OswBaseModel
from osw.wtsite import WtSite

# Definition of constants
PATTERNS = {
    "Category string with prefix in quotes": RegExPatternExtended(
        description='Match: "Category:<>"',
        pattern=r".*\"(Category:.+)\"",
        group_keys=["category"],
    ),
    "Category string with prefix in context and allOf": RegExPatternExtended(
        description="Match: /wiki/Category:<>?action",
        pattern=r"./wiki\/(Category:.+)\?action",
        group_keys=["category"],
    ),
    "Category string with prefix in brackets": RegExPatternExtended(
        description="Match: [[Category:<>]] and [[HasType::Category:<>]]",
        pattern=r"\[\[.*(Category:[a-zA-z0-9]+)\]\]",
        group_keys=["category"],
    ),
    "Property sting with prefix in quotes": RegExPatternExtended(
        description='Match: "Property:<>"',
        pattern=r"\"(Property:.+)\"",
        group_keys=["property"],
    ),
    "Property string with prefix and @id": RegExPatternExtended(
        description='Match: "@id": "Property:<>"',
        pattern=r'"@id":\s*\"(Property:.+)\"',
        group_keys=["property"],
    ),
    "Listed properties": RegExPatternExtended(
        description='Match: properties: ["<>", "<>"] and '
        'ignore_properties: ["<>", "<>"]',
        pattern=r"\"*properties\":\s*\[(\"[^\].]*\")\]",
        group_keys=["property"],
    ),
    "Property strings in autocomplete queries": RegExPatternExtended(
        description="Match: [[<Property>::Category:<Category>]]",
        pattern=r"\[\[([a-zA-Z\_]+)::.*\]\]",
        group_keys=["property"],
    ),
    "Property strings in general queries": RegExPatternExtended(
        description="Match: |?<Property>= and |<Property>=",
        pattern=r"\|[\?]*\s*([^\?^\=^#^\n^\{^\}^>^<^@]+)[\s\=\|\}]+",
        group_keys=["property"],
    ),
    "Template strings": RegExPatternExtended(
        description="Match: /wiki/JsonSchema:Label=action",
        pattern=r"\"\/wiki\/(.*:.*)\?action",
        group_keys=["template"],
    ),
}

PATTERNS_PER_SLOT = {
    "jsondata": [
        PATTERNS["Category string with prefix in quotes"],
        PATTERNS["Property sting with prefix in quotes"],
    ],
    "jsonschema": [
        PATTERNS["Category string with prefix in context and allOf"],
        PATTERNS["Category string with prefix in quotes"],
        PATTERNS["Property strings in autocomplete queries"],
        PATTERNS["Property strings in general queries"],
        PATTERNS["Property sting with prefix in quotes"],
        PATTERNS["Template strings"],
    ],
}
"""
    "footer_template": [
        PATTERNS["Listed properties"],
        PATTERNS["Property strings in autocomplete queries"],
        # This may cause way to many info box labels to end up in
        # the list of requirements:
        # PATTERNS["Property strings in general queries"],

    ],
    "header_template": [
        PATTERNS["Listed properties"],
        PATTERNS["Property strings in autocomplete queries"],
        # This may cause way to many info box labels to end up in
        # the list of requirements:
        # PATTERNS["Property strings in general queries"],
    ],
    "main": [
        PATTERNS["Category string with prefix in brackets"],
    ]
}
"""
# todo: consider only checking jsondata and jsonschema for requirements
#  + revise exceptions

EXCEPTIONS = [
    "de",
    "en",
    "#default",
    "format",
    "machine compatible name",
    "label",
    "short name",
    "mainlabel",
    "template",
    "named args",
    "Property",
    ",",
]

EXCEPTION_PATTERNS = {
    "Contains no capital letter": RegExPatternExtended(
        description="Match e.g.: 200x800px]]|",
        pattern=r"^[^A-Z]*$",
        group_keys=[],  # no group keys
    ),
}
"""
    "Contains backward slashes": RegExPatternExtended(
        description='Match: \\',
        pattern=r'\\',
        group_keys=[],  # no group keys
    ),
    "Contains forward slashes": RegExPatternExtended(
        description='Match: /',
        pattern='\\/',
        group_keys=[],  # no group keys
    ),
    "Contains brackets": RegExPatternExtended(
        description='Match e.g.: [[Category:OSWfe72974590fd4e8ba94cd4e8366375e8]]',
        pattern=r'[\\[\\]\\(\\)\\{\\}]+',
        group_keys=[],  # no group keys
    ),
    "Contains pipe char": RegExPatternExtended(
        description='Match e.g.: |',
        pattern=r'\\|',
        group_keys=[],  # no group keys
    ),
    "Contains quotation marks": RegExPatternExtended(
        description='Match e.g.: "',
        pattern=r'\\"',
        group_keys=[],  # no group keys
    ),
    "Contains hash": RegExPatternExtended(
        description='Match e.g.: "',
        pattern=r'#',
        group_keys=[],  # no group keys
    ),
}
"""


# Definition of functions
def import_module_from_file(module_name: str, file_path: Path):
    """Imports a module from a file. THis is usefull when the module
    has "." in the name!"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def read_package_info(script_fp: Path, package_name: str = None) -> dict:
    """Reads the package info from a script file"""
    if package_name is None:
        package_name = script_fp.stem.replace(".", "_").replace("-", "_")
    package_module = import_module_from_file(package_name, script_fp)
    return {
        "package_meta_data": package_module.package_meta_data,
        "package_creation_config": package_module.package_creation_config,
    }


def get_listed_pages_from_package_info(package_info: Union[dict, Path]) -> List[str]:
    """Takes in the output of read_package_info and returns a list of
    pages listed in the package"""
    if isinstance(package_info, Path):
        package_info = read_package_info_from_file(package_info)
    return package_info["package_meta_data"].page_titles


def read_package_info_from_file(
    package_dir: Path, package_info_fn: str = "packages.json"
) -> dict:
    """Reads the package info from a file in the package directory"""
    matching_files_in_dir = list(package_dir.glob(package_info_fn))
    if len(matching_files_in_dir) == 0:
        raise FileNotFoundError(f"No file {package_info_fn} found in {package_dir}")
    else:
        package_info_fp = matching_files_in_dir[0]
        with open(package_info_fp, "r") as package_info_fp:
            package_info = json.load(package_info_fp)
        return package_info


def get_listed_pages_from_package_info_file(
    package_info: Union[dict, Path]
) -> List[str]:
    """Takes in the output of read_package_info_from_file and returns a list of
    pages listed in the package"""
    if isinstance(package_info, Path):
        package_info = read_package_info_from_file(package_info)
    listed_pages = []
    for val in package_info["packages"].values():
        for page in val["pages"]:
            if page.get("namespace"):
                namespace = NAMESPACE_CONST_TO_NAMESPACE_MAPPING.get(page["namespace"])
            else:
                namespace = ""
            listed_pages.append(f"{namespace}:{page['name']}")
    return listed_pages


def get_required_packages_from_package_info_file(package_info: dict) -> List[str]:
    """Takes in the output of read_package_info_from_file and returns a list of
    packages listed in the package"""
    required_packages = []
    for val in package_info["packages"].values():
        if val.get("requiredPackages"):
            required_packages.extend(val["requiredPackages"])
    return required_packages


def check_for_exceptions(string: str) -> bool:
    """Checks if a string is listed as an exception or falls into
    an exception pattern."""
    is_exception = False
    # Check for empty string
    if len(string) == 0:
        return True
    for pattern in EXCEPTION_PATTERNS.values():
        if re.search(pattern.pattern.pattern, string):
            return True
    for exception_string in EXCEPTIONS:
        if string.lower() == exception_string:
            return True
    return is_exception


def get_required_pages_from_file(fp: Union[str, Path]) -> List[str]:
    """Returns a list of pages required by the package"""

    required_pages = []
    # suffix = fp.suffix
    pre_suffix = fp.suffixes[-2]
    slot_name = pre_suffix.split(".slot_")[-1]
    with open(fp, "r", encoding="utf-8") as f:
        content = f.read()
    if not PATTERNS_PER_SLOT.get(slot_name):
        return required_pages
    for pattern in PATTERNS_PER_SLOT.get(slot_name):
        match_res = re.findall(pattern.pattern.pattern, content, re.MULTILINE)
        if match_res:
            if "category" in pattern.group_keys:
                for match in match_res:
                    # if check_for_exceptions(match):
                    #     continue
                    required_pages.append(match)
            elif "property" in pattern.group_keys:
                for match in match_res:
                    # if check_for_exceptions(match):
                    #     continue
                    if '"' in match:
                        results = match.split('"')
                    else:
                        results = [match]
                    for res in results:
                        intermediate = []
                        if "-" in res:
                            intermediate.append(res.split("-")[-1])
                        elif "." or ":" in res:
                            intermediate.extend(res.split("."))
                            # intermediate.extend(res.split(":"))
                        else:
                            intermediate.append(res)
                        required_pages.extend(
                            [
                                "Property:" + s
                                for s in intermediate
                                if not s.startswith("Property:")
                                and not check_for_exceptions(s)
                            ]
                        )
            elif "template" in pattern.group_keys:
                for match in match_res:
                    # if check_for_exceptions(match):
                    #     continue
                    required_pages.append(match)
    return_obj = list(
        set(entry for entry in required_pages if not check_for_exceptions(entry))
    )
    return_obj.sort()
    return return_obj


# Definition of classes
class PagePackageController(model.PagePackageMetaData):
    """Adds controller logic to a package definitions to create / update it"""

    class CreationConfig(OswBaseModel):
        """Configuration for creating a page package. This is the data needed to create
        a page package but is not included in the page package."""

        domain: str
        """A string formatted as domain"""
        credentials_file_path: Union[str, FilePath]
        """Path to a existing credentials yaml files"""
        working_dir: Union[str, Path]
        """Working directory. Will be created automatically if not existing."""
        skip_slot_suffix_for_main: bool = False

    def create(
        self,
        creation_config: CreationConfig,
    ):
        """creates or updates the package

        Parameters
        ----------
        creation_config
            see PagePackageController.CreationConfig
        """
        # Create a WtSite instance to load pages from the specified domain
        wtsite = WtSite(
            WtSite.WtSiteConfig(
                iri=creation_config.domain,
                cred_mngr=CredentialManager(
                    cred_filepath=creation_config.credentials_file_path
                ),
            )
        )
        # Create a PagePackageBundle instance
        bundle = package.PagePackageBundle(
            publisher=self.publisher,
            author=self.author,
            language=self.language,
            publisherURL=f"https://github.com/{self.repo_org}/{self.repo}",
            packages={
                f"{self.name}": package.PagePackage(
                    globalID=f"{self.id}",
                    label=self.name,
                    version=self.version,
                    requiredExtensions=self.requiredExtensions,
                    requiredPackages=self.requiredPackages,
                    description=self.description,
                    baseURL=f"https://raw.githubusercontent.com/"
                    f"{self.repo_org}/"
                    f"{self.repo}/"
                    f"{self.branch}/"
                    f"{self.subdir}/",
                )
            },
        )
        # Create a PagePackageConfig instance
        config = package.PagePackageConfig(
            name=self.name,
            config_path=Path(creation_config.working_dir) / "packages.json",
            content_path=Path(creation_config.working_dir) / self.subdir,
            bundle=bundle,
            titles=self.page_titles,
            skip_slot_suffix_for_main=creation_config.skip_slot_suffix_for_main,
        )
        # Create the page package in the working directory
        wtsite.create_page_package(WtSite.CreatePagePackageParam(config=config))

    class GetRequiredPagesParams(OswBaseModel):
        creation_config: "PagePackageController.CreationConfig"
        direct_call: bool = True
        """Whether this function is called directly"""

    def get_required_pages(
        self, params: GetRequiredPagesParams
    ) -> Dict[str, Union[List[str], Dict[str, List[str]]]]:
        """Returns a list of pages required by the package"""

        required_pages_path = (
            Path(params.creation_config.working_dir) / "required_pages.json"
        )
        required_pages_dict = {}
        if required_pages_path.exists() and not params.direct_call:
            with open(required_pages_path, "r") as f:
                self.requiredPages = json.load(f)["list"]
        else:
            self.requiredPages = []
            content_path = Path(params.creation_config.working_dir) / self.subdir
            list_of_files = list(content_path.glob("**/*"))
            # parse the files
            for title in self.page_titles:
                required_pages_dict[title] = {}
                title_specific_files = [
                    file for file in list_of_files if title.split(":")[-1] in file.name
                ]
                for file in title_specific_files:
                    # For now: skip non (!) wikitext and json files
                    if file.suffix not in [".wikitext", ".json"]:
                        continue
                    pre_suffix = file.suffixes[-2]
                    slot_name = pre_suffix.split(".slot_")[-1]
                    required_pages = get_required_pages_from_file(file)
                    """File specific required pages"""
                    self.requiredPages.extend(required_pages)
                    if required_pages:
                        required_pages_dict[title][slot_name] = required_pages
                if not required_pages_dict[title]:  # test if empty
                    del required_pages_dict[title]
            # Remove duplicates
            self.requiredPages = list(set(self.requiredPages))
        self.requiredPages.sort()
        return_obj = {"list": self.requiredPages, "dict": required_pages_dict}
        with open(required_pages_path, "w", encoding="utf-8") as f:
            json.dump(return_obj, f, indent=4, ensure_ascii=False)

        return return_obj

    class CheckRequiredPagesParams(OswBaseModel):
        creation_config: "PagePackageController.CreationConfig"
        direct_call: bool = True
        """Whether this function is called directly and therefore to call get_required_pages()
        before checking for missing pages"""
        missing_pages: List[str] = None
        """List of pages that are missing in the package and packages listed as requiredPackages"""
        listed_pages: List[str] = None
        """List of pages that are listed in the package and packages listed as requiredPackages"""
        label_missing_pages: bool = None
        """Whether to get the labels of the missing pages from the OSW"""

        # class Config:
        #     arbitrary_types_allowed = True

    def check_required_pages(
        self,
        params: Union[CheckRequiredPagesParams, "PagePackageController.CreationConfig"],
    ):
        """Idea
        * Check which of the required pages are missing in the package
        * Check the list of pages in the packages.json of each package listed in requiredPackages
            * read the packages.json
            * navigate to ["packages"][0]["pages"]
            * list the pages here
                * read the namespace from the dict key "namespace"
                * use a dictionary
        * Check if the required pages are in the listed in the page package
        * Check if the required pages are also listed in the required pages of the required package
            * if the required_pages.json does not exist, create it
        * Report on missing dependencies
        """
        if isinstance(params, self.CreationConfig):
            params = self.CheckRequiredPagesParams(creation_config=params)
        if params.missing_pages is None:
            params.missing_pages = []
        if params.listed_pages is None:
            params.listed_pages = []
        if params.label_missing_pages is None:
            params.label_missing_pages = params.direct_call

        if params.direct_call:
            # Set self.requiredPages (either load from file or generate list)
            self.get_required_pages(
                PagePackageController.GetRequiredPagesParams(**params.dict())
            )

        def get_listed_pages_one_iter(
            listed_pages: List[str] = None,
            required_packages: List[str] = None,
            redundant_pages: Dict[str, list] = None,
        ) -> Dict[str, Union[List[str], Dict[str, list]]]:
            if listed_pages is None:
                listed_pages = []
            if required_packages is None:
                required_packages = []
            if redundant_pages is None:
                redundant_pages = {}
            new_required_packages = []
            for pck in required_packages:
                package_info = read_package_info_from_file(
                    params.creation_config.working_dir.parent / pck
                )
                new_listed_pages = get_listed_pages_from_package_info_file(package_info)
                new_redundant_pages = list(set(new_listed_pages) & set(listed_pages))
                listed_pages.extend(new_listed_pages)
                for pg in new_redundant_pages:
                    if redundant_pages.get(pg):
                        if pck not in redundant_pages[pg]:
                            redundant_pages[pg].append(pck)
                    else:
                        redundant_pages[pg] = [self.id, pck]
                new_required_packages.extend(
                    get_required_packages_from_package_info_file(package_info)
                )
            return {
                # Avoid duplicates:
                "listed_pages": list(set(listed_pages)),
                "required_packages": list(set(new_required_packages)),
                "redundant_pages": redundant_pages,
            }

        # Recursively list all page_titles of the required packages
        rec_params = {
            "listed_pages": self.page_titles,
            "required_packages": self.requiredPackages if self.requiredPackages else [],
            "redundant_pages": {},
        }
        while len(rec_params["required_packages"]) > 0:
            rec_params = get_listed_pages_one_iter(**rec_params)
        # Report on redundant pages
        for key in rec_params["redundant_pages"].keys():
            pks = rec_params["redundant_pages"][key]
            warn(f"Page {key} is listed in the more than one package!: {pks}")

        missing_pages = list(set(self.requiredPages) - set(rec_params["listed_pages"]))
        missing_pages.sort()
        # Save the missing pages to a file
        if params.direct_call:
            with open(
                Path(params.creation_config.working_dir) / "missing_pages.json",
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(missing_pages, f, indent=4, ensure_ascii=False)

        if params.label_missing_pages:
            # Reading missing pages from file if it already exists
            missing_pages_labeled_fp = (
                Path(params.creation_config.working_dir) / "missing_pages_labeled.json"
            )
            missing_pages_labeled = {}
            if missing_pages_labeled_fp.exists():
                with open(missing_pages_labeled_fp, "r", encoding="utf-8") as f:
                    missing_pages_labeled = json.load(f)
            pages_to_query = list(
                set(missing_pages) - set(missing_pages_labeled.keys())
            )  # pages that are not yet labeled
            if not len(pages_to_query) == 0:
                # Get the labels of the missing pages from the OSW
                wtsite_obj = WtSite(
                    WtSite.WtSiteConfig(
                        iri=params.creation_config.domain,
                        cred_mngr=CredentialManager(
                            cred_filepath=params.creation_config.credentials_file_path
                        ),
                    )
                )
                # Query pages
                pages = wtsite_obj.get_page(
                    WtSite.GetPageParam(titles=pages_to_query)
                ).pages
                # Process returned pages
                found_pages = {}
                for page in pages:
                    title = page.title
                    jsondata = page.get_slot_content("jsondata")
                    if jsondata is None:
                        label = "Page has no jsondata."
                    else:
                        label = "Page has no label."
                        if jsondata.get("label"):
                            label = jsondata["label"][0]["text"]
                    found_pages[title] = label
                # Add found pages to missing_pages_labeled
                for missing_page in missing_pages:
                    if not missing_pages_labeled.get(missing_page):
                        missing_pages_labeled[missing_page] = found_pages.get(
                            missing_page,
                            f"Page not found in {params.creation_config.domain}.",
                        )
            # missing_pages_labeled = {
            #     title: found_pages.get(
            #         title, f"Page not found in {params.creation_config.domain}."
            #     ) for title in missing_pages
            # }
            with open(missing_pages_labeled_fp, "w", encoding="utf-8") as f:
                json.dump(missing_pages_labeled, f, indent=4, ensure_ascii=False)


PagePackageController.CheckRequiredPagesParams.update_forward_refs()
PagePackageController.GetRequiredPagesParams.update_forward_refs()
