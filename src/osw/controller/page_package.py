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
    "File strings": RegExPatternExtended(
        description="Match: File:OSW<uuid>.<suffix>",
        pattern=r"(File:OSW[a-f0-9]{32}\.[^\\^\/^\"^\s]+)",
        group_keys=["file"],
    ),
    "Item strings": RegExPatternExtended(
        description="Match: Item:OSW<uuid>",
        pattern=r"(Item:OSW[a-f0-9]{32})",
        group_keys=["item"],
    ),
}

PATTERNS_PER_SLOT = {
    "jsondata": [
        PATTERNS["Category string with prefix in quotes"],
        PATTERNS["Property sting with prefix in quotes"],
        PATTERNS["Item strings"],
        PATTERNS["File strings"],
    ],
    "jsonschema": [
        PATTERNS["Category string with prefix in context and allOf"],
        PATTERNS["Category string with prefix in quotes"],
        PATTERNS["Property strings in autocomplete queries"],
        PATTERNS["Property strings in general queries"],
        PATTERNS["Property sting with prefix in quotes"],
        PATTERNS["Template strings"],
        PATTERNS["Item strings"],
        PATTERNS["File strings"],
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


def read_package_script_file(script_fp: Path, package_name: str = None) -> dict:
    """Reads the package info from a script file"""
    if package_name is None:
        package_name = script_fp.stem.replace(".", "_").replace("-", "_")
    package_module = import_module_from_file(package_name, script_fp)
    return {
        "package_meta_data": package_module.package_meta_data,
        "package_creation_config": package_module.package_creation_config,
        "package_creation_script_fp": script_fp,
    }


def get_listed_pages_from_package_script(package_script: dict) -> List[str]:
    """Takes in the output of read_package_script_file and returns a list of
    pages listed in the package"""
    return getattr(package_script["package_meta_data"], "page_titles")


def get_required_packages_from_package_script(package_script: dict) -> List[str]:
    """Takes in the output of read_package_script_file and returns a list of
    packages listed in the package"""
    if getattr(package_script["package_meta_data"], "requiredPackages"):
        return getattr(package_script["package_meta_data"], "requiredPackages")
    return []


def read_package_info_file(
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


def get_listed_pages_from_package_info(package_info: Union[dict, Path]) -> List[str]:
    """Takes in the output of read_package_info_file and returns a list of
    pages listed in the package"""
    if isinstance(package_info, Path):
        package_info = read_package_info_file(package_info)
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
    """Takes in the output of read_package_info_file and returns a list of
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
    try:
        pre_suffix = fp.suffixes[-2]
    except IndexError:
        pre_suffix = ".slot_main"

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
                    required_pages.append(match)
            elif "property" in pattern.group_keys:
                for match in match_res:
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
                                # only here to catch exceptions early
                            ]
                        )
            elif "template" in pattern.group_keys:
                for match in match_res:
                    required_pages.append(match)
            elif "item" in pattern.group_keys:
                for match in match_res:
                    required_pages.append(match)
            elif "file" in pattern.group_keys:
                for match in match_res:
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
                    try:
                        pre_suffix = file.suffixes[-2]
                    except IndexError:
                        pre_suffix = ".slot_main"
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
        """Whether this function is called directly and therefore to call
        get_required_pages() before checking for missing pages"""
        read_listed_pages_from_script: bool = False
        """Whether to read the listed pages and package info from the script
        file or from the package info file (default: packages.json)"""
        script_dir: Union[str, Path] = None
        """Path to the directory where the package creation script is stored.
        Only required if read_listed_pages_from_script is True"""
        label_missing_pages: bool = None
        """Whether to get the labels of the missing pages from the OSW"""

        # class Config:
        #     arbitrary_types_allowed = True

    def check_required_pages(
        self,
        params: CheckRequiredPagesParams,
    ):
        """Checks if all required pages are listed in the package and packages
        listed as requiredPackages. Simultaneously checks for redundant pages
        along the dependency chain.
        """
        if params.label_missing_pages is None:
            params.label_missing_pages = params.direct_call

        # Set self.requiredPages (either load from file or generate list)
        if params.direct_call:
            self.get_required_pages(
                PagePackageController.GetRequiredPagesParams(**params.dict())
            )
        # For debugging the recursive function
        rec_count = 0

        def recursive(
            package_to_process: str,
            processed_packages: List[str],
            listed_pages: Dict[str, List[str]],
            redundant_pages: Dict[str, List[str]],
        ):
            nonlocal rec_count
            rec_count += 1
            # else:
            if params.read_listed_pages_from_script:
                package_script = read_package_script_file(
                    params.script_dir / f"{package_to_process}.py"
                )
                new_listed_pages = get_listed_pages_from_package_script(package_script)
                required_packages = get_required_packages_from_package_script(
                    package_script
                )
            else:
                package_info = read_package_info_file(
                    params.creation_config.working_dir.parent / package_to_process
                )
                new_listed_pages = get_listed_pages_from_package_info(package_info)
                required_packages = get_required_packages_from_package_info_file(
                    package_info
                )
            # Check for redundant pages
            for pack_ in listed_pages.keys():
                new_redundant_pages = list(
                    set(new_listed_pages) & set(listed_pages[pack_])
                )
                for page_ in new_redundant_pages:
                    if redundant_pages.get(page_):
                        if pack_ not in redundant_pages[page_]:
                            redundant_pages[page_].append(package_to_process)
                    else:
                        redundant_pages[page_] = [pack_, package_to_process]
            # Add new listed pages to listed_pages
            listed_pages[package_to_process] = new_listed_pages
            # Document that this package has been processed
            processed_packages.append(package_to_process)
            # Prepare the return value
            return_val = {
                "processed_packages": processed_packages,
                "listed_pages": listed_pages,
                "redundant_pages": redundant_pages,
            }
            # Recursion Base case
            if len(required_packages) == 0:
                return return_val
            else:  # Recursion
                for pack_ in required_packages:
                    # Don't process packages that have already been processed
                    if pack_ in processed_packages:
                        continue
                    ret = recursive(
                        package_to_process=pack_,
                        processed_packages=processed_packages,
                        listed_pages=listed_pages,
                        redundant_pages=redundant_pages,
                    )
                    # Combine the returns
                    for pack__ in ret["listed_pages"].keys():
                        if return_val["listed_pages"].get(pack__):
                            return_val["listed_pages"][pack__].extend(
                                ret["listed_pages"][pack__]
                            )
                        else:
                            return_val["listed_pages"][pack__] = ret["listed_pages"][
                                pack__
                            ]
                    for pack__ in ret["processed_packages"]:
                        if pack__ not in return_val["processed_packages"]:
                            return_val["processed_packages"].append(pack__)
                    for page__ in ret["redundant_pages"].keys():
                        if return_val["redundant_pages"].get(page__):
                            for pack__ in ret["redundant_pages"][page__]:
                                if pack__ not in return_val["redundant_pages"][page__]:
                                    return_val["redundant_pages"][page__].append(pack__)
                        else:
                            return_val["redundant_pages"][page__] = ret[
                                "redundant_pages"
                            ][page__]

                return return_val

        # Call recursive function
        rec_ret = recursive(
            package_to_process=self.repo,
            processed_packages=[],
            listed_pages={},
            redundant_pages={},
        )
        # print(f"Recursive function called {rec_count} times.")
        # Report on redundantly listed pages
        for pg in rec_ret["redundant_pages"].keys():
            pks = rec_ret["redundant_pages"][pg]
            warn(f"Page {pg} is listed in {len(pks)} packages!: {pks}")
        # Get all listed pages
        all_listed_pages = []
        for pck in rec_ret["listed_pages"].keys():
            all_listed_pages.extend(rec_ret["listed_pages"][pck])
        # Check if all required pages are listed
        missing_pages = list(set(self.requiredPages) - set(all_listed_pages))
        missing_pages.sort()
        # Save the missing pages to a file
        if params.direct_call:
            with open(
                file=Path(params.creation_config.working_dir) / "missing_pages.json",
                mode="w",
                encoding="utf-8",
            ) as f:
                json.dump(missing_pages, f, indent=4, ensure_ascii=False)

        if params.label_missing_pages:
            # Reading missing page labels from file if it already exists
            missing_pages_labeled_fp = (
                Path(params.creation_config.working_dir) / "missing_pages_labeled.json"
            )
            prev_missing_page_labels = {}
            if missing_pages_labeled_fp.exists():
                with open(missing_pages_labeled_fp, "r", encoding="utf-8") as f:
                    prev_missing_page_labels = json.load(f)
            # Create a new dict for the labels of missing pages to avoid unwanted
            # migration of "old" keys
            missing_pages_labeled = {}
            # Only query pages that are not yet labeled
            pages_to_query = list(
                set(missing_pages) - set(list(prev_missing_page_labels.keys()))
            )  # pages that are not yet labeled

            found_pages = {}
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

            # Add found pages to missing_pages_labeled_new
            for page_ in missing_pages:
                if prev_missing_page_labels.get(page_):
                    missing_pages_labeled[page_] = prev_missing_page_labels[page_]
                elif found_pages.get(page_):
                    missing_pages_labeled[page_] = found_pages[page_]
                else:
                    missing_pages_labeled[page_] = (
                        f"Page not found in {params.creation_config.domain}."
                    )
            with open(missing_pages_labeled_fp, "w", encoding="utf-8") as f:
                json.dump(missing_pages_labeled, f, indent=4, ensure_ascii=False)


PagePackageController.CheckRequiredPagesParams.update_forward_refs()
PagePackageController.GetRequiredPagesParams.update_forward_refs()
