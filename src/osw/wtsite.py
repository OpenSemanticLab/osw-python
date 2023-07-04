"""Generic extension of mwclient.site, mainly to provide multi-slot page handling and
caching OpenSemanticLab specific features are located in osw.core.OSW
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from pprint import pprint
from time import sleep
from typing import Dict, List, Optional, Union

import mwclient
from jsonpath_ng.ext import parse
from pydantic import FilePath
from typing_extensions import deprecated

import osw.model.entity as model
import osw.model.page_package as package
import osw.utils.util as ut
import osw.wiki_tools as wt
from osw.auth import CredentialManager
from osw.model.static import OswBaseModel
from osw.utils.util import parallelize

# Constants
SLOTS = {
    "main": {"content_model": "wikitext", "content_template": ""},
    "header": {"content_model": "wikitext", "content_template": ""},
    "footer": {"content_model": "wikitext", "content_template": ""},
    "jsondata": {"content_model": "json", "content_template": ""},
    "jsonschema": {"content_model": "json", "content_template": ""},
    "template": {"content_model": "wikitext", "content_template": ""},
    "header_template": {"content_model": "wikitext", "content_template": ""},
    "footer_template": {"content_model": "wikitext", "content_template": ""},
    "data_template": {"content_model": "wikitext", "content_template": ""},
    "schema_template": {"content_model": "wikitext", "content_template": ""},
}


# Classes
class WtSite:
    """A wrapper class of mwclient.Site, mainly to provide multi-slot page handling and
    caching"""

    class WtSiteConfig(OswBaseModel):
        """The configuration for a WtSite instance"""

        iri: str
        """The IRI of the wiki site, typically the domain"""
        cred_mngr: CredentialManager
        """The CredentialManager to use for authentication"""
        login: Optional[str]
        """The preferred login name when multiple logins are possible (not supported
        yet)"""

    @deprecated("Use WtSiteConfig instead")
    class WtSiteLegacyConfig(OswBaseModel):
        """The legacy configuration for a WtSite instance"""

        site: mwclient.Site
        """the mwclient.Site to use for communication with the wiki"""

        class Config:
            arbitrary_types_allowed = True

    def __init__(self, config=Union[WtSiteConfig, WtSiteLegacyConfig]):
        """creates a new WtSite instance from a WtSiteConfig

        Parameters
        ----------
        config
            the WtSiteConfig or WtSiteLegacyConfig to create the WtSite from

        """
        if type(config) == WtSite.WtSiteLegacyConfig:
            self._site = config.site
        else:
            cred = config.cred_mngr.get_credential(
                CredentialManager.CredentialConfig(
                    iri=config.iri, fallback=CredentialManager.CredentialFallback.ask
                )
            )
            if type(cred) == CredentialManager.UserPwdCredential:
                self._site = mwclient.Site(cred.iri, path="/w/")
                self._site.login(username=cred.username, password=cred.password)
            elif type(cred) == CredentialManager.OAuth1Credential:
                self._site = mwclient.Site(
                    "wiki-dev.open-semantic-lab.org",
                    path="/w/",
                    consumer_token=cred.consumer_token,
                    consumer_secret=cred.consumer_secret,
                    access_token=cred.access_token,
                    access_secret=cred.access_secret,
                )
            else:
                raise ValueError("Unsupported credential type: " + str(type(cred)))
            del cred

        # The page cache is used to store pages that already have been loaded from
        #  the wiki
        self._page_cache = {}
        self._cache_enabled = False

    @classmethod
    @deprecated("Use contructor instead")
    def from_domain(
        cls,
        domain: str = None,
        password_file: Union[str, FilePath] = None,
        credentials: dict = None,
    ):
        """creates a new WtSite instance from a domain and a password file

        Parameters
        ----------
        domain, optional
            the wiki domain, by default None
        password_file, optional
            password file with credentials for the wiki site, by default None
        credentials, optional
            credentials of the wiki site, by default None

        Returns
        -------
            a new WtSite instance
        """
        if credentials is None:
            site = wt.create_site_object(domain, password_file)
        else:
            site = wt.create_site_object(domain, "", credentials)
        return cls(WtSite.WtSiteLegacyConfig(site=site))

    @classmethod
    @deprecated("Use contructor instead")
    def from_credentials(
        cls,
        credentials: Union[Dict[str, Dict[str, str]], str, FilePath],
        key: Union[str, int] = 0,
    ):
        """

        Parameters
        ----------
        credentials:
            A dictionary of credentials or a path to a credentials file, expected to
            contain keys 'username' and 'password'.
        key:
            The key of the credentials-dictionary (domain) or the index of the key.
            By default, the first key is used.

        Returns
        -------

        """

        if isinstance(credentials, str) or isinstance(credentials, Path):
            domains, accounts = wt.read_domains_from_credentials_file(credentials)
        else:
            accounts = credentials
        if isinstance(key, int):
            _domain = list(accounts.keys())[key]
        else:
            _domain = key
        _domain = _domain
        _credentials: Dict = accounts[_domain]
        # todo: research why nested typing doesn't work as expected fo the dictionary
        site = wt.create_site_object(_domain, "", _credentials)
        return cls(WtSite.WtSiteLegacyConfig(site=site))

    def get_WtPage(self, title: str = None):
        retry = 0
        max_retry = 5
        page = None
        while retry < max_retry:
            try:
                page = self._get_WtPage(title)
                break
            except Exception as e:
                print(e)
                if retry < max_retry:
                    retry += 1
                    print(f"Page load failed. Retry ({retry}/{max_retry})")
                    sleep(5)
        self._clear_cookies()
        return page

    def _get_WtPage(self, title: str = None):

        if self._cache_enabled and title in self._page_cache:
            return self._page_cache[title]
        else:
            wtpage = WtPage(self, title)
            if self._cache_enabled:
                self._page_cache[title] = wtpage

        return wtpage

    def enable_cache(self):
        self._cache_enabled = True

    def disable_cache(self):
        self._cache_enabled = False

    def get_cache_enabled(self):
        return self._cache_enabled

    def clear_cache(self):
        del self._page_cache
        self._page_cache = {}

    def _clear_cookies(self):
        # see https://github.com/mwclient/mwclient/issues/221
        for cookie in self._site.connection.cookies:
            if "PostEditRevision" in cookie.name:
                self._site.connection.cookies.clear(
                    cookie.domain, cookie.path, cookie.name
                )

    def prefix_search(self, text: Union[str, wt.SearchParam]):
        return wt.prefix_search(self._site, text)

    def semantic_search(self, query: Union[str, wt.SearchParam]):
        return wt.semantic_search(self._site, query)

    class ModifySearchResultsParam(model.OswBaseModel):
        mode: str
        query: wt.SearchParam
        comment: str = None
        log: bool = False
        dryrun: bool = False

    def modify_search_results(
        self,
        mode: str,
        query: str,
        modify_page,
        limit=None,
        comment=None,
        log=False,
        dryrun=False,
    ):
        titles = []
        if mode == "prefix":
            titles = wt.prefix_search(self._site, query)
        elif mode == "semantic":
            titles = wt.semantic_search(self._site, query)
        if limit:
            titles = titles[0:limit]
        if log:
            print(f"Found: {titles}")
        for title in titles:
            wtpage = self.get_WtPage(title)
            modify_page(wtpage)
            if log:
                print(f"\n======= {title} =======")
                print(wtpage._content)
                for slot in wtpage._slots:
                    content = wtpage.get_slot_content(slot)
                    # if isinstance(content, dict): content = json.dumps(content)
                    print(f"   ==== {title}:{slot} ====   ")
                    pprint(content)
                    print("\n")
            if not dryrun:
                wtpage.edit(comment)

    class UploadPageParam(model.OswBaseModel):
        pages: Union["WtPage", List["WtPage"]]
        parallel: Optional[bool] = False
        debug: Optional[bool] = False

        class Config:
            arbitrary_types_allowed = True

    def upload_page(
        self,
        param: Union[UploadPageParam, "WtPage", List["WtPage"]],
    ) -> None:
        """Uploads a page or a list of pages to the site.

        Parameters
        ----------
        param:
            UploadPageParam object or a WtPage object or a list of WtPage objects.
        """
        if isinstance(param, WtPage):
            param = WtSite.UploadPageParam(pages=[param])
        elif isinstance(param, list):
            param = WtSite.UploadPageParam(pages=param)

        max_index = len(param.pages)
        if max_index >= 5:
            param.parallel = True

        def upload_page_(page, index: int = None):
            # Before uploading: Check if the page is uploaded to the WtSite that is
            #  defining this method
            if page.wtSite != self:
                raise AssertionError(
                    f"The WtSite in page '{page.title}' and the "
                    f"WtSite from which this method is called from "
                    f"are not matching!"
                )
            page.edit()

            if index is None:
                print(f"Uploaded page to {page.get_url()}.")
            else:
                print(
                    f"({index + 1}/{max_index}): Uploaded page to " f"{page.get_url()}."
                )

        if param.parallel:
            _ = parallelize(upload_page_, param.pages, flush_at_end=param.debug)
        else:
            _ = [upload_page_(p, i) for i, p in enumerate(param.pages)]

    class CreatePagePackageParam(model.OswBaseModel):
        """Parameter object for create_page_package method."""

        config: package.PagePackageConfig
        """Configuration object for the page package."""
        dump_config: Optional["WtPage.PageDumpConfig"] = None
        """Configuration object for the page dump"""
        debug: Optional[bool] = True
        """If True, debug messages will be printed."""

        class Config:
            arbitrary_types_allowed = True

    def create_page_package(self, param: CreatePagePackageParam):
        """Create a page package, which is a locally stored collection of wiki pages
        and their slots, based on a configuration object.

        Parameters:
        -----------
        param:  CreatePagePackageParam
        """

        debug = param.debug
        dump_config = param.dump_config
        config = param.config

        # Clear the content directory
        try:
            if debug:
                print(f"Delete dir '{config.content_path}'")
            if os.path.exists(config.content_path):
                shutil.rmtree(config.content_path)
        except OSError as e:
            if debug:
                print("Error: %s - %s." % (e.filename, e.strerror))
        # Create a dump config
        if dump_config is None:
            dump_config = WtPage.PageDumpConfig(
                target_dir=config.content_path,
                skip_slot_suffix_for_main=config.skip_slot_suffix_for_main,
            )
        else:
            dump_config.target_dir = config.content_path
            dump_config.skip_slot_suffix_for_main = config.skip_slot_suffix_for_main

        bundle = config.bundle  # type: package.PagePackageBundle
        added_titles = []  # keep track of added pages, prevent duplicates

        if config.name not in bundle.packages:
            print(f"Error: package {config.name} does not exist in bundle")
            return
        if not bundle.packages[config.name].pages:
            bundle.packages[config.name].pages = []
        for title in config.titles:
            if title in added_titles:
                continue  # prevent duplicates
            else:
                added_titles.append(title)
            page = self.get_WtPage(title)
            bundle.packages[config.name].pages.append(page.dump(dump_config))
            if config.include_files:
                for file in page._page.images():
                    if file.name in added_titles:
                        continue  # prevent duplicates
                    else:
                        added_titles.append(file.name)
                    file_page = self.get_WtPage(file.name)
                    bundle.packages[config.name].pages.append(
                        file_page.dump(dump_config)
                    )

        content = bundle.json(exclude_none=True, indent=4)
        # This will create the JSON (e.g., package.json) with the PagePackageConfig,
        #  which contains the PagePackageBundle
        file_name = f"{config.config_path}"
        with open(file_name, "w") as f:
            f.write(content)

    class ReadPagePackageParam(model.OswBaseModel):
        """Parameter type of read_page_package."""

        storage_path: Union[str, Path]
        """The path to the directory where the page package is stored."""
        packages_info_file_name: Optional[Union[str, Path]] = None
        """The name of the file that contains the page package information. If not
            specified, the default value 'packages.json' is used."""
        selected_slots: Optional[List[str]] = None
        """A list of slots that should be read. If None, all slots are read."""
        debug: Optional[bool] = False
        """If True, debug information is printed to the console."""

    class ReadPagePackageResult(model.OswBaseModel):
        """Return type of read_page_package."""

        pages: List["WtPage"]
        """A list of WtPage objects."""

    def read_page_package(self, param: ReadPagePackageParam) -> ReadPagePackageResult:
        """Read a page package, which is a locally stored collection of wiki pages and
        their slots' content.

        Parameters
        ----------
        param: ReadPagePackageParam

        Returns
        -------
        result: ReadPagePackageResult
        """
        # map params
        storage_path = param.storage_path
        packages_info_file_name = param.packages_info_file_name
        selected_slots = param.selected_slots
        debug = param.debug
        # Test arguments / set default value
        if not os.path.exists(storage_path):
            raise FileNotFoundError(f"Storage path '{storage_path}' does not exist.")
        if not isinstance(storage_path, Path):
            storage_path = Path(storage_path)
        if packages_info_file_name is None:
            packages_info_file_name = "packages.json"
        # Get top level content of storage path
        top_level_content = ut.list_files_and_directories(
            search_path=storage_path, recursive=False
        )
        # Try to find packages info file in storage path
        pi_fp = os.path.join(storage_path, packages_info_file_name)
        # Check if packages info file exists in storage path, otherwise use fallback
        #  option or raise error
        if os.path.exists(pi_fp) and os.path.isfile(pi_fp):
            if debug:
                print(f"Found packages info file at '{pi_fp}'.")
        else:
            if debug:
                print(
                    f"Did not find packages info file at '{pi_fp}'. Trying default "
                    f"'packages.json'."
                )
            top_level_json_files = [
                f
                for f in top_level_content["files"]
                if f.is_file() and str(f).endswith(".json")
            ]
            json_in_top_level = ut.file_in_paths(
                paths=top_level_json_files, file_name="packages.json"
            )
            if json_in_top_level["found"]:
                pi_fp = json_in_top_level["file path"]
            elif len(top_level_json_files) > 0:
                if debug:
                    print(f"Found JSON files: {top_level_json_files}. Using first one.")
                pi_fp = top_level_json_files[0]
            else:
                raise FileNotFoundError(
                    f"Error: No JSON files found in '{storage_path}'."
                )
        # Read packages info file
        with open(pi_fp, "r") as f:
            packages_json = json.load(f)
        # Assume that the pages files are located in the subdir
        storage_path_content = ut.list_files_and_directories(
            search_path=storage_path, recursive=True
        )
        sub_dirs = top_level_content["directories"]
        if len(top_level_content["directories"]) == 0:
            # No subdirectories found, assume that the pages files are located in the
            #  top level
            sub_dirs = [storage_path]

        def get_slot_content(
            parent_dir: List[Union[str, Path]],
            url_path: str,
            files_in_storage_path: List[Path],
        ) -> Union[str, Dict]:
            for pdir in parent_dir:
                slot_path = storage_path / pdir / url_path
                if slot_path in files_in_storage_path:
                    with open(slot_path, "r") as f:
                        file_content = f.read()
                    # Makes sure not to open an empty file with json
                    if len(file_content) > 0:
                        if url_path.endswith(".json"):
                            with open(slot_path, "r") as f:
                                slot_data = json.load(f)
                            return slot_data
                        elif url_path.endswith(".wikitext"):
                            slot_data = file_content
                            return slot_data

        # Create WtPage objects
        pages = []
        for package_name, package_dict in packages_json["packages"].items():
            for page in package_dict["pages"]:
                namespace = page["namespace"].split("_")[-1].capitalize()
                name = page["name"]
                # Create the WtPage object
                page_obj = WtPage(wtSite=self, title=f"{namespace}:{name}")
                if "main" in selected_slots:
                    # Main slot is special
                    slot_content = get_slot_content(
                        parent_dir=sub_dirs,
                        url_path=page["urlPath"],
                        files_in_storage_path=storage_path_content["files"],
                    )
                    if slot_content is not None:
                        page_obj.set_slot_content(
                            slot_key="main",
                            content=slot_content,
                        )
                if selected_slots is None:
                    _selected_slots = page["slots"]
                else:
                    _selected_slots = {
                        slot_name: slot_dict
                        for slot_name, slot_dict in page["slots"].items()
                        if slot_name in selected_slots
                    }
                for slot_name, slot_dict in _selected_slots.items():
                    slot_content = get_slot_content(
                        parent_dir=sub_dirs,
                        url_path=slot_dict["urlPath"],
                        files_in_storage_path=storage_path_content["files"],
                    )
                    if slot_content is not None:
                        page_obj.set_slot_content(
                            slot_key=slot_name,
                            content=slot_content,
                        )
                pages.append(page_obj)
        return WtSite.ReadPagePackageResult(page_list=pages)

    class UploadPagePackageParam(model.OswBaseModel):
        """Parameter class for upload_page_package method."""

        storage_path: Optional[Union[str, Path]] = None
        """The path to the storage directory.
        If 'storage_path' is not given, 'pages' must be given."""
        pages: Optional[List["WtPage"]] = None
        """A list of WtPage objects.
        If 'pages' is not given, 'storage_path' must be given."""
        debug: Optional[bool] = False
        """If True, prints debug information."""

    def upload_page_package(self, param: UploadPagePackageParam):
        """Uploads a page package to the wiki defined by a list of WtPage objects or
        a storage path.

        Parameters
        ----------
        param : UploadPagePackageParam

        """
        storage_path = param.storage_path
        pages = param.pages
        debug = param.debug

        if storage_path and pages is None:
            raise ValueError(
                "Error: If 'storage_path' is not given, 'pages' must be given."
            )
        if pages is None:
            pages = self.read_page_package(
                WtSite.ReadPagePackageParam(storage_path=storage_path, debug=debug)
            ).pages
        for page in pages:
            page.edit()

    def get_file_pages(self, limit: int = 1000000) -> List[str]:
        """Get all file pages in the wiki"""
        full_page_titles = wt.prefix_search(
            site=self._site,
            text=wt.SearchParam(query="File:", debug=False, limit=limit),
        )
        return full_page_titles

    def get_file_info_and_usage(
        self,
        page_titles: Union[str, List[str], wt.SearchParam],
    ) -> list:
        """Get the file info and usage for one or more file pages.

        Parameters
        ----------
        page_titles:
            One or more full page titles of file pages or wiki_tools.SearchParam.

        Returns
        -------
        result:
            Dictionary with page titles as keys and nested dictionary with keys 'info'
            and 'usage'.
        """
        if isinstance(page_titles, str):
            title = wt.SearchParam(query=[page_titles], debug=False, parallel=True)
        elif isinstance(page_titles, list):
            title = wt.SearchParam(query=page_titles, debug=False, parallel=True)
        else:  # SearchParam
            title = page_titles
        return wt.get_file_info_and_usage(site=self._site, title=title)


class WtPage:
    def __init__(self, wtSite: WtSite = None, title: str = None):
        self.wtSite = wtSite
        self.title = title

        self._page = wtSite._site.pages[self.title]
        self.exists = self._page.exists
        self._original_content = ""
        self._content = ""
        self.changed: bool = False
        self._dict = []  # todo: named dict but is of type list
        self._slots: Dict[str, Union[str, dict]] = {"main": ""}
        self._slots_changed: Dict[str, bool] = {"main": False}
        self._content_model: Dict[str, str] = {"main": "wikitext"}

        if self.exists:
            self._original_content = self._page.text()
            self._content = self._original_content
            self._dict = wt.create_flat_content_structure_from_wikitext(
                self._content, array_mode="only_multiple"
            )
            # multi content revisions
            rev = wtSite._site.api(
                "query",
                prop="revisions",
                titles=title,
                rvprop="ids|timestamp|flags|comment|user|content|contentmodel|roles|"
                "slotsize|slotsha1",
                rvslots="*",
                rvlimit="1",
                format="json",
            )
            for page_id in rev["query"]["pages"]:
                page = rev["query"]["pages"][page_id]
                if page["title"] == title:
                    for revision in page["revisions"]:
                        self._current_revision = revision
                        for slot_key in revision["slots"]:
                            self._slots[slot_key] = revision["slots"][slot_key]["*"]
                            self._content_model[slot_key] = revision["slots"][slot_key][
                                "contentmodel"
                            ]
                            self._slots_changed[slot_key] = False
                            # self._slots_sha1[slot_key] = \
                            #     revision["slots"][slot_key]["*"]
                            if self._content_model[slot_key] == "json":
                                self._slots[slot_key] = json.loads(
                                    self._slots[slot_key]
                                )
                    # todo: set content for slots not in revision["slots"] (use
                    #  SLOTS) --> create empty slots

    def create_slot(self, slot_key, content_model):
        self._slots[slot_key] = {}
        # To avoid TypeError: argument of type 'NoneType' is not iterable in
        #  set_slot_content()
        self._slots_changed[slot_key] = False
        self._content_model[slot_key] = content_model

    def get_content(self):
        return self._content

    def get_slot_content(self, slot_key):
        if slot_key not in self._slots:
            return None
        return self._slots[slot_key]

    def get_slot_content_model(self, slot_key):
        if slot_key not in self._slots:
            return None
        return self._content_model[slot_key]

    def set_content(self, content):
        self._content = content
        self.changed = True

    def set_slot_content(self, slot_key, content):
        if slot_key not in self._slots:
            slot_dict = SLOTS.get(slot_key, None)
            if slot_dict is None:
                raise ValueError(
                    f"Error: Slot '{slot_key}' not defined in 'SLOTS'."
                    f"Available slots: {list(SLOTS.keys())}"
                )
            content_model = slot_dict["content_model"]
            self.create_slot(slot_key, content_model)
        if content != self._slots[slot_key]:
            self._slots_changed[slot_key] = True
        self._slots[slot_key] = content

    def get_url(self) -> str:
        return "https://" + self.wtSite._site.host + "/wiki/" + self.title

    def is_file_page(self) -> bool:
        """Checks if this page is a file page (containing an image, pdf, etc.)

        Returns
        -------
            true if this page is a file page, else false
        """
        return self.title.startswith("File:")

    def append_template(self, template_name: str = None, template_params: dict = None):
        self._dict.append({template_name: template_params})
        return self

    def append_text(self, text):
        self._dict.append(text)
        return self

    def get_value(self, jsonpath):
        jsonpath_expr = parse(jsonpath)
        res = []
        d = dict(
            zip(range(len(self._dict)), self._dict)
        )  # convert list to dict with index
        for match in jsonpath_expr.find(d):
            res.append(match.value)
        return res

    def update_dict(self, combined: dict, update: dict) -> None:
        for k, v in update.items():
            if isinstance(v, dict):
                # todo: fix reference for combine_into
                WtPage.combine_into(v, combined.setdefault(k, {}))
            else:
                combined[k] = v

    def set_value(self, jsonpath_match, value, replace=False):
        jsonpath_expr = parse(jsonpath_match)
        d = dict(
            zip(range(len(self._dict)), self._dict)
        )  # convert list to dict with index
        # if create: jsonpath_expr.update_or_create(d, value)
        # else: jsonpath_expr.update(d, value)
        matches = jsonpath_expr.find(d)
        for match in matches:
            print(match.full_path)
            # pprint(value)
            if not replace:
                WtPage.update_dict(match.value, value)
                value = match.value
            # pprint(value)
            match.full_path.update_or_create(d, value)
        self._dict = list(d.values())  # convert dict with index to list
        return self

    def update_content(self):
        self._content = wt.get_wikitext_from_flat_content_structure(self._dict)
        self.changed = self._original_content != self._content
        return self

    def edit(self, comment: str = None, mode="action-multislot"):
        """Creates / updates the content of all page slots in the wiki site

        Parameters
        ----------
        comment:
            (optional) edit comment for the page history, by default None
        mode:
            (optional) single API call ('action-multislot') or multiple (
            'action-singleslot'), by default 'action-multislot' (faster)
        """
        retry = 0
        max_retry = 5
        while retry < max_retry:
            try:
                return self._edit(comment, mode)
            except Exception as e:
                print(e)
                if retry < max_retry:
                    retry += 1
                    print(f"Page edit failed. Retry ({retry}/{max_retry})")
                    sleep(5)

    def _edit(self, comment: str = None, mode="action-multislot"):
        if not comment:
            comment = "[bot] update of page content"
        if self.changed:
            self._page.edit(self._content, comment)  # legacy mode
        if mode == "action-multislot":
            params = {}
            changed = False
            for slot_key in self._slots:
                if self._slots_changed[slot_key]:
                    changed = True
                    self._slots_changed[slot_key] = False
                    content = self._slots[slot_key]
                    if self._content_model[slot_key] == "json":
                        if not isinstance(content, str):
                            content = json.dumps(content)
                    params["slot_" + slot_key] = content
            if changed:
                self.wtSite._site.api(
                    "editslots",
                    token=self.wtSite._site.get_token("csrf"),
                    title=self.title,
                    summary=comment,
                    **params,
                )
                self.wtSite._clear_cookies()

        else:
            for slot_key in self._slots:
                if self._slots_changed[slot_key]:
                    content = self._slots[slot_key]
                    if self._content_model[slot_key] == "json":
                        content = json.dumps(content)
                    self.wtSite._site.api(
                        "editslot",
                        token=self.wtSite._site.get_token("csrf"),
                        title=self.title,
                        slot=slot_key,
                        text=content,
                        summary=comment,
                    )
                    self._slots_changed[slot_key] = False

    def delete(self, comment: str = None):
        self._page.delete(comment)

    def move(self, new_title: str, comment: str = None, redirect=True):
        if new_title != self.title:
            print(f"move '{self.title}' to '{new_title}'")
            self._page.move(
                new_title=new_title, reason=comment, no_redirect=not redirect
            )
            self.title = new_title

    def get_last_changed_time(self):
        return datetime.fromisoformat(
            self._current_revision["timestamp"].replace("Z", "+00:00")
        )

    class PageDumpConfig(model.OswBaseModel):
        """Configuration to dump wiki pages to the file system"""

        target_dir: Union[str, Path]
        """Directory to dump all contents.
        Will be created automatically if not existing"""
        namespace_as_folder: Optional[bool] = True
        """Store page contents in subfolders named according to their namespaces"""
        skip_slot_suffix_for_main: Optional[bool] = False
        """If true, do not include 'main' in the generated content file.
        Useful for pages / wikis using only the main slot."""
        dump_empty_slots: Optional[bool] = False
        """If true, dump all configured slots even empty ones.
        Useful to create initial content in these slots."""
        page_name_as_filename: Optional[bool] = False
        """Use the (human readable) name of a page also for the file naming.
        Useful to identify dumped files manually. The mapping to the page title/id
        (in general a UUID) is ensured anyway through package.json meta data."""

        class Config:
            arbitrary_types_allowed = True  # necessary to allow e.g. np.array as type

    def dump(self, config: PageDumpConfig) -> package.PagePackagePage:
        """Dump this page to the file system

        Parameters
        ----------
        config
            see WtPage.PageDumpConfig

        Returns
        -------
            Metadata of the generated dump
        """
        page_name = self.title.split(":")[-1]
        if ":" in self.title:
            namespace = self.title.split(":")[0]
        else:
            namespace = "Main"

        namespace_const = "NS_" + namespace.upper()
        if namespace in package.NAMESPACE_TO_NAMESPACE_CONST_MAPPING:
            namespace_const = package.NAMESPACE_TO_NAMESPACE_CONST_MAPPING[namespace]

        package_page = package.PagePackagePage(
            name=page_name, namespace=namespace_const, slots={}
        )
        name_in_json_data = False
        if "jsondata" in self._slots and "name" in self._slots["jsondata"]:
            package_page.label = self._slots["jsondata"]["name"]
            name_in_json_data = True

        if config.page_name_as_filename and name_in_json_data:
            # Use name from jsondata as filename for the dump
            dump_name = self._slots["jsondata"]["name"]
        else:
            # Use page name as filename for the dump
            dump_name = page_name

        tar_dir = config.target_dir
        path_prefix = ""
        if config.namespace_as_folder:
            tar_dir = os.path.join(tar_dir, namespace)
            path_prefix = namespace + "/"
        # if not os.path.exists(dir):
        #    os.makedirs(dir)

        def save_to_file(file_path__, content__):
            if not os.path.exists(os.path.dirname(file_path__)):
                os.makedirs(os.path.dirname(file_path__))
            with open(os.path.join(file_path__), "w", encoding="utf-8") as f__:
                f__.write(content__)

        def dump_slot_content(slot_key_, content_type_, content_):
            if isinstance(content_, dict):
                content_ = json.dumps(content_, indent=4)
            if content_type_ == "Scribunto":
                content_type_ = "lua"
            if slot_key_ == "main" and config.skip_slot_suffix_for_main:
                file_name_ = f"{dump_name}.{content_type_}"
            else:
                file_name_ = f"{dump_name}.slot_{slot_key_}.{content_type_}"
            # handle subpages:
            file_path_ = os.path.join(tar_dir, *file_name_.split("/"))
            save_to_file(file_path_, content_)
            if slot_key_ == "main":
                package_page.urlPath = path_prefix + file_name_
            else:
                package_page.slots[slot_key_] = package.PagePackagePageSlot(
                    urlPath=path_prefix + file_name_
                )

        for slot_key in self._slots:
            content = self.get_slot_content(slot_key)
            content_type = self.get_slot_content_model(slot_key)
            dump_slot_content(slot_key, content_type, content)

        # If the slots are empty, we still want files to fill after dumping them
        if config.dump_empty_slots:
            for slot_key in [slot for slot in SLOTS.keys() if slot not in self._slots]:
                content = SLOTS[slot_key]["content_template"]
                content_type = SLOTS[slot_key]["content_model"]
                dump_slot_content(slot_key, content_type, content)

        if self.is_file_page():
            file = self.wtSite._site.images[self.title.split(":")[-1]]
            file_name = f"{page_name}"
            file_path = os.path.join(tar_dir, *file_name.split("/"))  # handle subpages
            with open(file_path, "wb") as fd:
                file.download(fd)
            package_page.fileURLPath = path_prefix + file_name

        return package_page

    def get_file_info_and_usage(
        self, debug: bool = False
    ) -> Dict[str, Union[str, List[str]]]:
        return wt.get_file_info_and_usage(
            site=self.wtSite._site,
            title=wt.SearchParam(query=self.title, debug=debug),
        )[0]

    def purge(self):
        self._page.purge()


# Updating forwards refs in pydantic models
WtSite.UploadPageParam.update_forward_refs()
