"""Generic extension of mwclient.site, mainly to provide multi-slot page handling and
caching OpenSemanticLab specific features are located in osw.core.OSW
"""

import json
import os
import shutil
import urllib
import warnings
import xml.etree.ElementTree as et
from copy import deepcopy
from datetime import datetime
from io import StringIO
from pathlib import Path
from pprint import pprint
from time import sleep
from typing import Any, Dict, List, Optional, Union

import mwclient
import pyld
import requests
from jsonpath_ng.ext import parse
from pydantic.v1 import FilePath
from typing_extensions import deprecated

import osw.model.page_package as package
import osw.utils.util as ut
import osw.wiki_tools as wt
from osw.auth import CredentialManager
from osw.model.static import OswBaseModel
from osw.utils.regex_pattern import REGEX_PATTERN_LIB
from osw.utils.util import parallelize
from osw.utils.wiki import get_osw_id

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
        connection_options: Optional[Dict[str, Any]] = None
        """Parameters for the mwclient.Site connection: Additional arguments to be
        passed to the requests.Session.request() method when performing API calls."""

    @deprecated("Use WtSiteConfig instead")
    class WtSiteLegacyConfig(OswBaseModel):
        """The legacy configuration for a WtSite instance"""

        site: mwclient.Site
        """the mwclient.Site to use for communication with the wiki"""

        class Config:
            arbitrary_types_allowed = True

    def __init__(self, config: Union[WtSiteConfig, WtSiteLegacyConfig]):
        """creates a new WtSite instance from a WtSiteConfig

        Parameters
        ----------
        config
            the WtSiteConfig or WtSiteLegacyConfig to create the WtSite from

        """

        scheme = "https"

        if isinstance(config, WtSite.WtSiteLegacyConfig):
            self._site = config.site
        else:
            cred = config.cred_mngr.get_credential(
                CredentialManager.CredentialConfig(
                    iri=config.iri, fallback=CredentialManager.CredentialFallback.ask
                )
            )
            if "//" in config.iri:
                scheme = config.iri.split("://")[0]
                config.iri = config.iri.split("://")[1]
            site_args = [config.iri]
            # increase pool_maxsize to improve performance with many requests to the same server
            # see: https://stackoverflow.com/questions/18466079/change-the-connection-pool-size-for-pythons-requests-module-when-in-threading # noqa
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_maxsize=50)
            session.mount(scheme + "://", adapter)
            # verify=False is necessary for self-signed / outdated certificates
            site_kwargs = {
                "path": "/w/",
                "scheme": scheme,
                "pool": session,
                "do_init": False,  # do not initialize the site metadata for performance reasons
                "connection_options": {
                    "verify": True,
                },
            }
            if getattr(config, "connection_options", None) is not None:
                # merge connection_options into reqs
                site_kwargs["connection_options"] = {
                    **site_kwargs["connection_options"],
                    **config.connection_options,
                }
                # reqs might be a deprecated alias for "connection_options"
            if isinstance(cred, CredentialManager.UserPwdCredential):
                self._site = mwclient.Site(*site_args, **site_kwargs)
                self._site.login(username=cred.username, password=cred.password)
            elif isinstance(cred, CredentialManager.OAuth1Credential):
                site_kwargs.update(
                    **{
                        "consumer_token": cred.consumer_token,
                        "consumer_secret": cred.consumer_secret,
                        "access_token": cred.access_token,
                        "access_secret": cred.access_secret,
                    }
                )
                self._site = mwclient.Site(*site_args, **site_kwargs)
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

    class GetPageParam(OswBaseModel):
        titles: Union[str, List[str]]
        """title string or list of title strings of the pages to download"""
        parallel: Optional[bool] = None
        """whether to download the pages in parallel or sequentially
        Defaults to True if more than 5 pages are requested, False otherwise"""
        retries: Optional[int] = 5
        """How often to retry downloading a page if an error occurs"""
        retry_delay_s: Optional[int] = 5
        """Retry delay in seconds"""
        debug: Optional[bool] = False
        """Whether to print debug messages"""
        raise_exception: Optional[bool] = False
        """Whether to raise an exception if an error occurs"""
        raise_warning: Optional[bool] = True
        """Whether to raise a warning if a page does not exist occurs"""

        def __init__(self, **data):
            super().__init__(**data)
            if not isinstance(self.titles, list):
                self.titles = [self.titles]
            if len(self.titles) > 5 and self.parallel is None:
                self.parallel = True
            if self.parallel is None:
                self.parallel = False

    class GetPageResult(OswBaseModel):
        pages: List["WtPage"]
        """List of pages that have been downloaded"""
        errors: List[Exception]
        """List of errors that occurred while downloading pages"""

        class Config:
            arbitrary_types_allowed = True  # allows to use WtPage in type hints

    def get_page(self, param: GetPageParam) -> GetPageResult:
        """Downloads a page or a list of pages from the site.

        Parameters
        ----------
        param:
            GetPageParam object
        """
        max_index = len(param.titles)

        exceptions = []
        pages = []

        def get_page_(title: str, index: int = None):
            retry = 0
            wtpage = None
            while retry < param.retries:
                msg = ""
                if index is not None:
                    msg = f"({index + 1}/{max_index}) "
                try:
                    if self._cache_enabled and title in self._page_cache:
                        wtpage = self._page_cache[title]
                        msg += "Page loaded from cache. "
                    else:
                        wtpage = WtPage(self, title)
                        msg += "Page loaded. "
                        if self._cache_enabled:
                            self._page_cache[title] = wtpage
                    pages.append(wtpage)
                    if not wtpage.exists:
                        if param.raise_warning:
                            warnings.warn(
                                "WARNING: Page with title '{}' does not exist.".format(
                                    title
                                ),
                                RuntimeWarning,
                                3,
                            )
                        # throw argument value exception if page does not exist
                        raise ValueError(f"Page with title '{title}' does not exist.")

                    break
                except Exception as e:
                    exceptions.append(e)
                    msg += str(e)
                    # retry if probably a network error and retry limit not reached
                    if not isinstance(e, ValueError) and retry < param.retries:
                        retry += 1
                        msg = f"Page load failed: '{e}'. Retry ({retry}/{param.retries}). "
                        sleep(5)
                    else:  # last entry -> throw exception
                        retry = param.retries
                        if param.raise_exception:
                            raise e
                print(msg)
            self._clear_cookies()
            return wtpage

        if param.parallel:
            _ = parallelize(get_page_, param.titles, flush_at_end=param.debug)
        else:
            _ = [get_page_(p, i) for i, p in enumerate(param.titles)]

        return self.GetPageResult(pages=pages, errors=exceptions)

    @deprecated("Use get_page instead")
    def get_WtPage(self, title: str = None):
        """Creates a new WtPage object for the given title
           and loads the page from the site if the page already exists.
           Deprecated in favor of WtSite.get_page.

        Parameters
        ----------
        title:
            title of the page to load / create

        """
        result = self.get_page(WtSite.GetPageParam(titles=title))
        return result.pages[0]

    class GetPageContentResult(OswBaseModel):
        contents: dict
        """The content of the pages. Keys are page titles, values are
        content dictionaries"""

        class Config:
            arbitrary_types_allowed = True

    def get_page_content(self, full_page_titles: List[str]) -> GetPageContentResult:
        get_page_res = self.get_page(WtSite.GetPageParam(titles=full_page_titles))
        contents_dict = {}
        for page in get_page_res.pages:
            title = page.title
            slot_contents = {}
            for slot in SLOTS:
                slot_content = page.get_slot_content(slot)
                if slot_content is not None:
                    slot_contents[slot] = slot_content
            contents_dict[title] = slot_contents

        return WtSite.GetPageContentResult(contents=contents_dict)

    def enable_cache(self):
        """Enables the page cache. If the cache is enabled, pages that have been
        downloaded once are stored in memory and are not downloaded again
        """
        self._cache_enabled = True

    def disable_cache(self):
        """Disables the page cache. If the cache is disabled, pages are downloaded
        every time they are requested
        """
        self._cache_enabled = False

    def get_cache_enabled(self):
        """Returns whether the page cache is enabled

        Returns
        -------
        bool
            whether the page cache is enabled
        """
        return self._cache_enabled

    def clear_cache(self):
        """Clears the page cache. All pages that have been downloaded are removed from
        the cache
        """
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
        """Send a prefix search request to the site.

        Parameters
        ----------
        text
            The search text or a SearchParam object

        Returns
        -------
            A list of page titles
        """
        return wt.prefix_search(self._site, text)

    def semantic_search(self, query: Union[str, wt.SearchParam]):
        """Send a swm ask query to the site.

        Parameters
        ----------
        query
            The query text (e. g. "[[Category:Entity]]") or a SearchParam object

        Returns
        -------
            A list of page titles
        """
        return wt.semantic_search(self._site, query)

    class ModifySearchResultsParam(OswBaseModel):
        """Todo: should become param of modify_search_results"""

        mode: str
        """The search mode. Either 'prefix' or 'semantic'."""
        query: wt.SearchParam
        """The search query."""
        comment: str = None
        """The comment for the edit."""
        log: bool = False
        """Whether to log changes."""
        dryrun: bool = False
        """if True, no actual changes are made"""

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
        """Modifies the search results of a prefix or semantic search in a callback and
        stores the changes.

        Parameters
        ----------
        mode
            The search mode. Either 'prefix' or 'semantic'.
        query
            The search query.
        modify_page
            The callback that modifies the pages.
        limit, optional
            query limit, by default None
        comment, optional
            edit comment, by default None
        log, optional
            log changes, by default False
        dryrun, optional
            if True, no actual changes are made, by default False
        """
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
            wtpage = self.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
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

    class UploadPageParam(OswBaseModel):
        """Parameter object for upload_page method."""

        pages: Union["WtPage", List["WtPage"]]
        """A WtPage object or a list of WtPage objects."""
        parallel: Optional[bool] = False
        """If True, uploads the pages in parallel."""
        debug: Optional[bool] = False
        """If True, debug messages will be printed."""

        class Config:
            arbitrary_types_allowed = True

        def __init__(self, **data):
            super().__init__(**data)
            if not isinstance(self.pages, list):
                self.pages = [self.pages]
            if len(self.pages) > 5 and self.parallel is None:
                self.parallel = True
            if self.parallel is None:
                self.parallel = False

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
        if not isinstance(param, WtSite.UploadPageParam):
            param = WtSite.UploadPageParam(pages=param)

        max_index = len(param.pages)

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

    class CopyPagesParam(OswBaseModel):
        """Configuration to copy several page"""

        source_site: "WtSite"
        """The source site to copy the pages from"""
        existing_pages: Union[str, List[str]]
        """The full page title of the pages on the source site"""
        overwrite: Optional[bool] = False
        """If true, pages will be overwritten if they already exists on the target
        site"""
        parallel: Optional[bool] = None
        """If true, uploads the pages in parallel."""
        comment: Optional[str] = None
        """Edit comment for the page history. If set to none, will be replaced with
        '[bot edit] Copied from {source_site.host}'."""

        class Config:
            arbitrary_types_allowed = True

        def __init__(self, **data):
            super().__init__(**data)
            if not isinstance(self.existing_pages, list):
                self.existing_pages = [self.existing_pages]
            if len(self.existing_pages) > 5 and self.parallel is None:
                self.parallel = True
            if self.parallel is None:
                self.parallel = False

    def copy_pages(self, param: CopyPagesParam):
        """Copies pages from a source site to this (target) site."""

        def copy_single_page(content_dict: dict):
            title = list(content_dict.keys())[0]
            wtpage = WtPage(wtSite=self, title=title)
            return wtpage.copy(
                config=WtPage.CopyPageConfig(
                    source_site=param.source_site,
                    existing_page=title,
                    overwrite=param.overwrite,
                    comment=param.comment,
                )
            )

        page_contents = param.source_site.get_page_content(param.existing_pages)
        content_list = [{key: value} for key, value in page_contents.contents.items()]

        if param.parallel:
            return ut.parallelize(
                copy_single_page,
                content_list,
                flush_at_end=True,
            )
        else:
            return [copy_single_page(content) for content in content_list]

    class CreatePagePackageParam(OswBaseModel):
        """Parameter object for create_page_package method."""

        config: package.PagePackageConfig
        """Configuration object for the page package."""
        dump_config: Optional["WtPage.PageDumpConfig"] = None
        """Configuration object for the page dump"""
        debug: Optional[bool] = True
        """If True, debug messages will be printed."""
        parallel: Optional[bool] = None
        """If true, processes the pages in parallel."""

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

        bundle: package.PagePackageBundle = config.bundle
        added_titles = []  # keep track of added pages, prevent duplicates

        if config.name not in bundle.packages:
            print(f"Error: package {config.name} does not exist in bundle")
            return
        if not bundle.packages[config.name].pages:
            bundle.packages[config.name].pages = []
        # remove duplicates while keeping order
        added_titles = list(dict.fromkeys(config.titles))

        pages = self.get_page(
            WtSite.GetPageParam(titles=added_titles, parallel=param.parallel)
        ).pages
        added_file_titles = []
        page_dumps = {}
        page_files = {}

        for page in pages:
            # Appends an item of type: package.PagePackagePage:
            page_dumps[page.title] = page.dump(dump_config)
            if config.include_files:
                referenced_file_pages = page.find_file_page_refs_in_slots()
                if debug and len(referenced_file_pages) > 0:
                    print(
                        f"File pages referenced in {page.title}: {referenced_file_pages}"
                    )
                if param.config.ignore_titles is not None:
                    included_file_pages = list(
                        set(referenced_file_pages) - set(param.config.ignore_titles)
                    )
                    # print ignored files
                    ignored_files_pages = list(
                        set(referenced_file_pages) - set(included_file_pages)
                    )
                    if debug and len(ignored_files_pages) > 0:
                        print(f"Ignored: {ignored_files_pages}")
                    referenced_file_pages = included_file_pages
                # find those files that are not already in the package
                page_files[page.title] = list(
                    set(referenced_file_pages) - set(added_file_titles)
                )
                added_file_titles = list(set(added_file_titles + referenced_file_pages))

        file_dumps = {}
        if len(added_file_titles) > 0:
            file_pages = self.get_page(
                WtSite.GetPageParam(titles=added_file_titles, parallel=param.parallel)
            ).pages
            for file_page in file_pages:
                if not file_page.exists:
                    continue
                # ToDo: Make this parallel as well
                file_dumps[file_page.title] = file_page.dump(dump_config)

        # bring it all together
        for page_title in added_titles:
            if page_title in page_dumps:
                bundle.packages[config.name].pages.append(page_dumps[page_title])
            if page_title in page_files:
                for file_title in page_files[page_title]:
                    if file_title in file_dumps:
                        bundle.packages[config.name].pages.append(
                            file_dumps[file_title]
                        )

        content = bundle.json(exclude_none=True, indent=4, ensure_ascii=False)
        # This will create the JSON (e.g., package.json) with the PagePackageConfig,
        #  which contains the PagePackageBundle
        file_name = f"{config.config_path}"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(content)

    class ReadPagePackageParam(OswBaseModel):
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

    class ReadPagePackageResult(OswBaseModel):
        """Return type of read_page_package."""

        pages: List["WtPage"]
        """A list of WtPage objects."""

        class Config:
            arbitrary_types_allowed = True

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
        with open(pi_fp, "r", encoding="utf-8") as f:
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
                    with open(slot_path, "r", encoding="utf-8") as f:
                        file_content = f.read()
                    # Makes sure not to open an empty file with json
                    if len(file_content) > 0:
                        if url_path.endswith(".json"):
                            with open(slot_path, "r", encoding="utf-8") as f:
                                slot_data = json.load(f)
                            return slot_data
                        elif url_path.endswith(".wikitext"):
                            slot_data = file_content
                            return slot_data

        # Create WtPage objects
        pages = []
        for _package_name, package_dict in packages_json["packages"].items():
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
        return WtSite.ReadPagePackageResult(pages=pages)

    class UploadPagePackageParam(OswBaseModel):
        """Parameter class for upload_page_package method."""

        storage_path: Optional[Union[str, Path]] = None
        """The path to the storage directory.
        If 'storage_path' is not given, 'pages' must be given."""
        pages: Optional[List["WtPage"]] = None
        """A list of WtPage objects.
        If 'pages' is not given, 'storage_path' must be given."""
        debug: Optional[bool] = False
        """If True, prints debug information."""

        class Config:
            arbitrary_types_allowed = True

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

    def get_prefix_dict(self):
        """Returns a dictionary with the custom prefixes used in osl"""
        prefix_dict = {
            "Property": "https://{domain}/id/Property-3A",
            "File": "https://{domain}/id/File-3A",
            "Category": "https://{domain}/id/Category-3A",
            "Item": "https://{domain}/id/Item-3A",
            "wiki": "https://{domain}/id/",
        }
        for prefix in prefix_dict:
            prefix_dict[prefix] = prefix_dict[prefix].replace(
                "{domain}", self._site.host
            )
        return prefix_dict

    def get_jsonld_context_prefixes(self):
        """Returns a dictionary with the custom prefixes used in osl for jsonld context"""
        context = {}
        for prefix, iri in self.get_prefix_dict().items():
            context[prefix] = {
                "@id": iri,
                "@prefix": True,
            }
        return context

    class JsonLdContextLoaderParams(OswBaseModel):
        prefer_external_vocal: Optional[bool] = True
        """Whether to prefer external vocabularies (e.g. skos, schema, etc.)
        over the local properties (Namespace 'Property:')"""

    def _replace_jsonld_context_mapping(
        self, context: Union[str, list, dict], config: JsonLdContextLoaderParams
    ):
        """
        interate over a jsonld context
        set <prefix> to the value of <prefix>* if not set yet
        handle string, list and dict values
        handle mappings direct to iri as well as
        {"@id": "http://example.org/property", @type": "@id"} and scoped contexts
        """
        if isinstance(context, str):
            return context
        if isinstance(context, list):
            return [self._replace_jsonld_context_mapping(e, config) for e in context]
        if isinstance(context, dict):
            context_iter = context.copy()
            for key in context_iter:
                value = context[key]
                if key == "wiki":
                    context[key] = f"https://{self._site.host}/id/"
                    # print(f"apply https://{self._site.host}/id/ to {key}")
                if isinstance(value, str):
                    base_key = key.split("*")[0]
                    if base_key not in context:
                        context[base_key] = value
                        # print(f"apply {key} to {base_key}")
                    if config.prefer_external_vocal is False:
                        base_mapping = context[base_key]
                        if isinstance(base_mapping, dict):
                            base_mapping = base_mapping["@id"]
                        mapping = value
                        if mapping.startswith(
                            "Property:"
                        ) and not base_mapping.startswith("Property:"):
                            context[base_key] = value
                            # print(f"apply {key} to {base_key}")
                elif isinstance(value, list):
                    context[key] = [
                        self._replace_jsonld_context_mapping(e, config) for e in value
                    ]
                elif isinstance(value, dict):
                    if "@id" in value:
                        base_key = key.split("*")[0]
                        if base_key not in context:
                            context[base_key] = value
                            # print(f"apply {key} to {base_key}")
                        if config.prefer_external_vocal is False:
                            base_mapping = context[base_key]
                            if isinstance(base_mapping, dict):
                                base_mapping = base_mapping["@id"]
                            mapping = value["@id"]
                            if mapping.startswith(
                                "Property:"
                            ) and not base_mapping.startswith("Property:"):
                                context[base_key] = value
                                # print(f"apply {key} to {base_key}")
                    elif "@context" in value:
                        context[key] = self._replace_jsonld_context_mapping(
                            value["@context"], config
                        )
            return context

    def get_jsonld_context_loader(self, params: JsonLdContextLoaderParams = None):
        if params is None:
            params = self.JsonLdContextLoaderParams()

        """to overwrite the default jsonld document loader to load
        relative context from the osl"""

        def loader(url, options=None):
            if options is None:
                options = {}
            # print("Requesting", url)
            if "/wiki/" in url:
                title = url.split("/wiki/")[-1].split("?")[0]
                page = self.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
                if "JsonSchema:" in title:
                    schema = page.get_slot_content("main")
                else:
                    schema = page.get_slot_content("jsonschema")
                if isinstance(schema, str):
                    schema = json.loads(schema)
                schema["@context"] = self._replace_jsonld_context_mapping(
                    schema["@context"], params
                )

                doc = {
                    "contentType": "application/json",
                    "contextUrl": None,
                    "documentUrl": url,
                    "document": schema,
                }
                # print("Loaded", doc)
                return doc

            else:
                requests_loader = (
                    pyld.documentloader.requests.requests_document_loader()
                )
                return requests_loader(url, options)

        return loader


class WtPage:
    """A wrapper class of mwclient.page, mainly to provide multi-slot page handling"""

    def __init__(self, wtSite: WtSite = None, title: str = None, do_init: bool = True):
        """Creates a new WtPage object for the given title and loads the page from the
        site if the page already exists.

        Parameters
        ----------
        wtSite, optional
            The instance site object, by default None
        title, optional
            the page title, by default None
        do_init, optional
            whether to initialize the page, by default True
        """
        self.wtSite = wtSite
        self.title = title

        self._original_content = ""
        self._content = ""
        self.changed: bool = False
        self._dict = []  # todo: named dict but is of type list
        self._slots: Dict[str, Union[str, dict]] = {"main": ""}
        self._slots_changed: Dict[str, bool] = {"main": False}
        self._content_model: Dict[str, str] = {"main": "wikitext"}

        if do_init:
            self.init()

    def init(self):
        """Initializes the page by loading the content and meta data from the site"""
        # inits the mwclient object - triggers an API call
        self._page = self.wtSite._site.pages[self.title]
        self.exists = self._page.exists

        if self.exists:
            self._original_content = self._page.text()
            self._content = self._original_content
            # multi content revisions
            # second API call - ToDo: combine / replace with first call
            rev = self.wtSite._site.api(
                "query",
                prop="revisions",
                titles=self.title,
                rvprop="ids|timestamp|flags|comment|user|content|contentmodel|roles|"
                "slotsize|slotsha1",
                rvslots="*",
                rvlimit="1",
                format="json",
            )
            for page_id in rev["query"]["pages"]:
                page = rev["query"]["pages"][page_id]
                if page["title"] == self.title:
                    for revision in page["revisions"]:
                        self._current_revision = revision
                        if "slots" in revision:
                            for slot_key in revision.get("slots", {}):
                                self._slots[slot_key] = revision["slots"][slot_key]["*"]
                                self._content_model[slot_key] = revision["slots"][
                                    slot_key
                                ]["contentmodel"]
                                self._slots_changed[slot_key] = False
                                # self._slots_sha1[slot_key] = \
                                #     revision["slots"][slot_key]["*"]
                                if self._content_model[slot_key] == "json":
                                    self._slots[slot_key] = json.loads(
                                        self._slots[slot_key]
                                    )
                        else:  # legacy MW instances < 1.35
                            self._slots["main"] = revision["*"]
                            self._content_model["main"] = "wikitext"
                            self._slots_changed["main"] = False
                            # self._slots_sha1["main"] = revision["sha1"]
                    # todo: set content for slots not in revision["slots"] (use
                    #  SLOTS) --> create empty slots

    def parse_main_slot(self):
        """Parses the main slot content of the page
        Requires wikitext dependencies installed with 'pip install osw[wikitext]'
        """
        self._dict = wt.create_flat_content_structure_from_wikitext(
            self._content, array_mode="only_multiple"
        )

    def create_slot(self, slot_key, content_model):
        """Creates a new slot for the page. Availables Keys and content models are defined in
        SLOTS.

        Parameters
        ----------
        slot_key
            The key of the slot (e.g. 'header', 'footer', 'jsondata', etc.)
        content_model
            The content model of the slot (wikitext, json, etc.)
        """
        self._slots[slot_key] = {}
        # To avoid TypeError: argument of type 'NoneType' is not iterable in
        #  set_slot_content()
        self._slots_changed[slot_key] = False
        self._content_model[slot_key] = content_model

    @deprecated("Use get_slot_content('main') instead")
    def get_content(self):
        """Get the content of the page (slot: main). Should be replaced by
        get_slot_content('main')
        Note: The content is parsed at page initialization with
        wt.create_flat_content_structure_from_wikitext()

        Returns
        -------
            _description_
        """
        return self._content

    def get_slot_content(self, slot_key, clone: bool = True):
        """Get the content of a slot

        Parameters
        ----------
        slot_key
            The key of the slot.
        clone
            Whether to return a pointer to the slot of the page or a clone (copy).

        Returns
        -------
            the content of the slot
        """
        if slot_key not in self._slots:
            return None
        if clone:
            return deepcopy(self._slots[slot_key])
        return self._slots[slot_key]

    def get_parsed_slot_content(self, slot_key: str) -> List:
        """Gets the parsed content of a slot by calling
        wt.create_flat_content_structure_from_wikitext()
        Parsed content can be set with set_parsed_slot_content().

        Parameters
        ----------
        slot_key
            the key of the slot

        Returns
        -------
            the parsed content of the slot
        """
        content = self.get_slot_content(slot_key)
        content = wt.create_flat_content_structure_from_wikitext(content)
        return content

    def get_slot_content_model(self, slot_key):
        """Get the content model of a slot

        Parameters
        ----------
        slot_key
            The key of the slot.

        Returns
        -------
            the content model of the slot
        """
        if slot_key not in self._slots:
            return None
        return self._content_model[slot_key]

    @deprecated("Use set_slot_content('main', content) instead")
    def set_content(self, content):
        """Sets the content of the page (slot: main). Should be replaced by
        set_slot_content('main', content)

        Parameters
        ----------
        content
            The new content of the page
        """
        self._content = content
        self.changed = True

    def set_slot_content(self, slot_key, content):
        """Sets the content of a slot

        Parameters
        ----------
        slot_key
            The key of the slot
        content
            the new content of the slot

        Raises
        ------
        ValueError
            if the slot_key is not defined in SLOTS
        """
        if slot_key not in self._slots:
            slot_dict = SLOTS.get(slot_key, None)
            if slot_dict is None:
                raise ValueError(
                    f"Error: Slot '{slot_key}' not defined in 'SLOTS'."
                    f"Available slots: {list(SLOTS.keys())}"
                )
            content_model = slot_dict["content_model"]
            self.create_slot(slot_key, content_model)
        if self._content_model[slot_key] == "json":
            new_content_str = json.dumps(content, ensure_ascii=False)
            original_content_str = json.dumps(self._slots[slot_key], ensure_ascii=False)
            if new_content_str != original_content_str:
                self._slots_changed[slot_key] = True
        else:
            if content != self._slots[slot_key]:
                self._slots_changed[slot_key] = True
        self._slots[slot_key] = content

    def set_parsed_slot_content(self, slot_key: str, content: List):
        """Sets the parsed content of a slot by calling
        wt.get_wikitext_from_flat_content_structure().
        Parsed content can be retrieved with get_parsed_slot_content()
        or wt.create_flat_content_structure_from_wikitext().

        Parameters
        ----------
        slot_key
            the key of the slot
        content
            the new parsed content of the slot
        """
        content = wt.get_wikitext_from_flat_content_structure(content)
        self.set_slot_content(slot_key, content)

    def get_url(self) -> str:
        """Get the URL of the page

        Returns
        -------
            the URL of the page
        """
        return "https://" + self.wtSite._site.host + "/wiki/" + self.title

    def is_file_page(self) -> bool:
        """Checks if this page is a file page (containing an image, pdf, etc.)

        Returns
        -------
            true if this page is a file page, else false
        """
        return self.title.startswith("File:")

    @deprecated("No longer supported")
    def append_template(self, template_name: str = None, template_params: dict = None):
        """Appends a wiki template to the parsed main slot content.
        Please note that the main slots is parsed at page initialization
        with wt.create_flat_content_structure_from_wikitext().
        Remember to call update_content() afterwards

        Parameters
        ----------
        template_name, optional
            the name of the template, by default None
        template_params, optional
            the parameters of the template, by default None

        Returns
        -------
            the WtPage object
        """
        self._dict.append({template_name: template_params})
        return self

    @deprecated("No longer supported")
    def append_text(self, text):
        """Appends text to the parsed main slot content.
        Please note that the main slots is parsed at page initialization
        with wt.create_flat_content_structure_from_wikitext().
        Remember to call update_content() afterwards

        Parameters
        ----------
        text:
            the text to append

        Returns
        -------
            the WtPage object
        """
        self._dict.append(text)
        return self

    @deprecated("No longer supported")
    def get_value(self, jsonpath):
        """Resolves a JSONPath expression in the parsed main slot content.
        Please note that the main slots is parsed at page initialization
        with wt.create_flat_content_structure_from_wikitext().

        Parameters
        ----------
        jsonpath
            The JSONPath expression

        Returns
        -------
            The query result
        """
        jsonpath_expr = parse(jsonpath)
        res = []
        d = dict(
            zip(range(len(self._dict)), self._dict)
        )  # convert list to dict with index
        for match in jsonpath_expr.find(d):
            res.append(match.value)
        return res

    @deprecated("No longer supported")
    def update_dict(self, combined: dict, update: dict) -> None:
        for k, v in update.items():
            if isinstance(v, dict):
                # todo: fix reference for combine_into
                wt.combine_into(v, combined.setdefault(k, {}))
            else:
                combined[k] = v

    @deprecated("No longer supported for replace=False")
    def set_value(self, jsonpath_match, value, replace=False):
        """Sets the value of a JSONPath expression in the parsed main slot content.
        Please note that the main slots is parsed at page initialization
        with wt.create_flat_content_structure_from_wikitext().
        Remember to call update_content() afterwards

        Parameters
        ----------
        jsonpath_match
            The JSONPath expression
        value
            The value to set
        replace, optional
            Whether to replace the value, by default False

        Returns
        -------
            The WtPage object
        """
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

    @deprecated("Use set_parsed_slot_content('main', content) instead")
    def update_content(self):
        """Updates the content of the page with the parsed content of the main slots
        by calling wt.get_wikitext_from_flat_content_structure().

        Returns
        -------
            the WtPage object
        """
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
                if retry < max_retry:
                    retry += 1
                    print(f"Page edit failed: {e}. Retry ({retry}/{max_retry})")
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
                            content = json.dumps(content, ensure_ascii=False)
                    params["slot_" + slot_key] = content
            if changed:
                self.changed = True
                self.wtSite._site.api(
                    "editslots",
                    token=self.wtSite._site.get_token("csrf"),
                    title=self.title,
                    summary=comment,
                    **params,
                )
                self.wtSite._clear_cookies()

        else:
            changed = False
            for slot_key in self._slots:
                if self._slots_changed[slot_key]:
                    changed = True
                    content = self._slots[slot_key]
                    if self._content_model[slot_key] == "json":
                        content = json.dumps(content, ensure_ascii=False)
                    self.wtSite._site.api(
                        "editslot",
                        token=self.wtSite._site.get_token("csrf"),
                        title=self.title,
                        slot=slot_key,
                        text=content,
                        summary=comment,
                    )
                    self._slots_changed[slot_key] = False
            if changed:
                self.changed = True

    def delete(self, comment: str = None):
        """Deletes the page from the site

        Parameters
        ----------
        comment, optional
            The delete comment, by default None
        """
        self._page.delete(comment)

    def move(self, new_title: str, comment: str = None, redirect=True):
        """Moves (=renames) the page to a new title

        Parameters
        ----------
        new_title
            the new title of the page
        comment, optional
            the edit comment
        redirect, optional
            whether to create a redirect from the old title to the new title
        """
        if new_title != self.title:
            print(f"move '{self.title}' to '{new_title}'")
            self._page.move(
                new_title=new_title, reason=comment, no_redirect=not redirect
            )
            self.title = new_title

    def get_last_changed_time(self):
        """Gets the timestamp of the last change of the page

        Returns
        -------
            a datetime string in ISO format
        """
        return datetime.fromisoformat(
            self._current_revision["timestamp"].replace("Z", "+00:00")
        )

    class CopyPageConfig(OswBaseModel):
        """Configuration to copy a page"""

        source_site: WtSite
        """The source site to copy the page from"""
        existing_page: str
        """The full page title of the page on the source site"""
        overwrite: Optional[bool] = False
        """If true, the page will be overwritten if it already exists on the target
        site"""
        comment: Optional[str] = None
        """Edit comment for the page history"""

        class Config:
            arbitrary_types_allowed = True

    class PageCopyResult(OswBaseModel):
        """Result of copying a page"""

        page: "WtPage"
        """The copied page"""
        target_altered: bool
        """True if the page at the target site was altered"""

        class Config:
            arbitrary_types_allowed = True

    def copy(self, config: CopyPageConfig) -> PageCopyResult:
        if config.comment is None:
            config.comment = f"[bot edit] Copied from {config.source_site._site.host}"
        result = config.source_site.get_page_content([config.existing_page])
        for title, slot_contents in result.contents.items():
            self.title = title
            verb = "created"
            if self.exists:
                verb = "updated"
                if config.overwrite is False:
                    return WtPage.PageCopyResult(page=self, target_altered=False)
                changed_slots = []
                for slot in SLOTS:
                    if self.get_slot_content(slot) != slot_contents.get(slot, None):
                        changed_slots.append(slot)
                if len(changed_slots) == 0:
                    print(
                        f"Page '{self.title}' already has the same content. It will "
                        f"not be updated."
                    )
                    return WtPage.PageCopyResult(page=self, target_altered=False)
                else:
                    print(
                        f"Page '{self.title}' has different content in slots "
                        f"{changed_slots}."
                    )
            for slot in slot_contents.keys():
                self.create_slot(
                    slot_key=slot, content_model=SLOTS[slot]["content_model"]
                )
                self.set_slot_content(slot_key=slot, content=slot_contents[slot])
            self.edit(comment=config.comment)
            s2p = f"Page {verb}: 'https://{self.wtSite._site.host}/wiki/{self.title}'."
            if verb == "updated":
                s2p = (
                    f"Page {verb}: 'https://{self.wtSite._site.host}/w/index.php?title"
                    f"={self.title}&action=history'."
                )
            print(s2p)
            return WtPage.PageCopyResult(page=self, target_altered=True)

    class PageDumpConfig(OswBaseModel):
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
                content_ = json.dumps(content_, indent=4, ensure_ascii=False)
            if content_type_ == "Scribunto":
                content_type_ = "lua"
            if slot_key_ == "main" and config.skip_slot_suffix_for_main:
                file_name_ = f"{dump_name}.{content_type_}"
            else:
                file_name_ = f"{dump_name}.slot_{slot_key_}.{content_type_}"
            # handle subpages:
            file_path_ = os.path.join(tar_dir, *file_name_.split("/"))
            save_to_file(file_path_, content_)
            # generate url encoded path for the page package
            if slot_key_ == "main":
                package_page.urlPath = urllib.parse.quote(path_prefix + file_name_)
            else:
                package_page.slots[slot_key_] = package.PagePackagePageSlot(
                    urlPath=urllib.parse.quote(path_prefix + file_name_)
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
            # The following will return KeyError "url" if the file is not found
            with open(file_path, "wb") as fd:
                file.download(fd)
            package_page.fileURLPath = path_prefix + file_name

        return package_page

    def get_file_info_and_usage(
        self, debug: bool = False
    ) -> Dict[str, Union[str, List[str]]]:
        """For file page only: Get the file info and usage for this file page

        Parameters
        ----------
        debug
            Whether to print debug information, by default False

        Returns
        -------
            Dictionary with page titles as keys and nested dictionary with keys 'info'
            and 'usage'.
        """
        return wt.get_file_info_and_usage(
            site=self.wtSite._site,
            title=wt.SearchParam(query=self.title, debug=debug),
        )[0]

    def find_file_page_refs_in_slots(self, slots: List[str] = None) -> List[str]:
        """Find all file page references in the content of the given slots."""
        if slots is None:
            slots = list(self._slots.keys())
        file_page_refs = []
        for slot in slots:
            # get slot content
            content = self.get_slot_content(slot)
            if content is None:
                continue
            # find all file page references
            pattern = REGEX_PATTERN_LIB["File page strings from any text"]
            full_page_names = pattern.findall_by_group_key(
                str(content),  # make sure its a string not a dictionary
                "Full page name",
            )
            file_page_refs.extend(full_page_names)
            # Find all files in editor templates
            pattern = REGEX_PATTERN_LIB["File uuid in template"]
            res = pattern.finditer(str(content))
            # Iterate over all matches
            for match in res:
                ft = None
                # Check if the match has the groups "Editor" and "UUID" and UUID is a
                #  valid OSW ID
                try:
                    if "Editor" in match.groups and "UUID" in match.groups:
                        # construct a file page title
                        osw_id = get_osw_id(match.groups["UUID"])
                        if match.groups["Editor"] == "DrawIO":
                            ft = "File:" + osw_id + ".drawio.svg"
                        elif match.groups["Editor"] == "SvgEdit":
                            ft = "File:" + osw_id + ".svg"
                        elif match.groups["Editor"] == "Kekule":
                            ft = "File:" + osw_id + ".kekule.json"
                        elif match.groups["Editor"] == "Spreadsheet":
                            ft = "File:" + osw_id + ".luckysheet.json"
                        elif match.groups["Editor"] == "Wellplate":
                            ft = "File:" + osw_id + ".wellplate.svg"
                    if ft is not None:
                        file_page_refs.append(ft)
                except ValueError:
                    print("Warning: Error while parsing uuid in editor template")
        return list(set(file_page_refs))

    def purge(self):
        """Purge the page from the site cache.
        Triggers a rebuild / refresh of the page.
        This is useful if the page content is changed and the changes are not visible
        """
        self._page.purge()

    class ExportConfig(OswBaseModel):
        """Configuration to export a page to XML"""

        full_history: Optional[bool] = True
        """if true, export the full history of the page, else only the current revision"""
        include_templates: Optional[bool] = False
        """if true, export the templates used in the page"""

    class ExportResult(OswBaseModel):
        """Return type of export_xml"""

        xml: str
        """the XML string"""
        success: bool
        """if true, the export was successful, else false"""

    def export_xml(self, config: Optional[ExportConfig] = None) -> ExportResult:
        """Exports the page to XML

        Parameters
        ----------
        config, optional
            see ExportConfig

        Returns
        -------
            ExportResult
        """
        if config is None:
            config = WtPage.ExportConfig()
        url = (
            self.wtSite._site.scheme
            + "://"
            + self.wtSite._site.host
            + self.wtSite._site.path
            + "index.php?title=Special:Export/"
            + self.title
        )
        data = {
            "title": "Special:Export",
            "catname": "",
            "pages": self.title,
            "wpEditToken": self.wtSite._site.get_token("csrf"),
            "wpDownload": "1",
        }
        if not config.full_history:
            data["curonly"] = "1"
        if config.include_templates:
            data["templates"] = "1"
        response = self.wtSite._site.connection.post(url, data=data)
        if response.status_code != 200:
            return WtPage.ExportResult(success=False, xml="")
        else:
            return WtPage.ExportResult(success=True, xml=response.text)

    class ImportConfig(OswBaseModel):
        """Configuration to import a page from XML.
        see also https://www.mediawiki.org/wiki/Manual:Importing_XML_dumps"""

        xml: str
        """the XML string to import (see WtPage.export_xml)"""
        summary: str
        """the edit summary to use for the import"""
        source_domain: str
        """the domain of the instance from which the XML was exported, e.g. mywiki.com"""
        full_history: Optional[bool] = True
        """if true, import the full history of the page, else only the current revision"""
        include_templates: Optional[bool] = False
        """if true, import the templates used in the page if contained in the XML"""
        namespace_mapping: Optional[Dict[str, str]] = {
            "Main": 0,
            "File": 6,
            "Template": 10,
            "Category": 14,
            "Item": 7000,
        }
        """mapping of namespaces names to IDs in the target instance"""
        username_mapping: Optional[Dict[str, str]] = {}
        """mapping of usernames in the XML to usernames in the target instance"""

    class ImportResult(OswBaseModel):
        """Return type of import_xml"""

        success: bool
        """if true, the import was successful, else false"""
        imported_title: str
        imported_revisions: int
        error_msg: Optional[str] = None

    def import_xml(self, config: ImportConfig) -> ImportResult:
        """Imports the page from an XML export

        Parameters
        ----------
        config
            see ImportConfig

        Returns
        -------
            ExportResult
        """

        # Remove default namespace definition (see https://stackoverflow.com/questions/
        #  34009992/python-elementtree-default-namespace)
        config.xml = config.xml.replace(
            'xmlns="http://www.mediawiki.org', '_xmlns="http://www.mediawiki.org'
        )
        print(config.xml)
        tree = et.fromstring(config.xml)

        # Replace title and namespace with the requested ones
        tree.find(".//title").text = self.title.split(":")[1]
        tree.find(".//ns").text = str(
            config.namespace_mapping.get(self.title.split(":")[0], 0)
        )
        # Apply username mapping (user in the target system might have different names)
        for e in tree.findall(".//username"):
            e.text = config.username_mapping.get(e.text, e.text)

        config.xml = et.tostring(tree, encoding="unicode")
        # Restore default namespace definition
        config.xml = config.xml.replace(
            '_xmlns="http://www.mediawiki.org', 'xmlns="http://www.mediawiki.org'
        )

        api_url = (
            self.wtSite._site.scheme
            + "://"
            + self.wtSite._site.host
            + self.wtSite._site.path
            + "api.php"
        )
        response = self.wtSite._site.connection.post(
            url=api_url,
            data={
                "action": "import",
                "token": self.wtSite._site.get_token("csrf"),
                "fullhistory": "1" if config.full_history else "0",
                "templates": "1" if config.include_templates else "0",
                "assignknownusers": "1",
                "interwikiprefix": config.source_domain,
                # "namespace": self.title.split(":")[0],
                "summary": config.summary,
                "format": "json",
            },
            files={
                "xml": (
                    "xml",
                    StringIO(config.xml),
                    "text/xml",
                )  # read config.xml as file
            },
        )

        json = response.json()
        if "error" in json:
            # print("Error: ", json)
            return WtPage.ImportResult(success=False, error_msg=json["error"]["info"])
        else:
            # print("Imported: ", json["import"][0]["title"], " with ",
            #       json["import"][0]["revisions"], " revisions")
            return WtPage.ImportResult(
                success=True,
                imported_title=json["import"][0]["title"],
                imported_revisions=json["import"][0]["revisions"],
            )


# Updating forwards refs in pydantic models
WtPage.PageCopyResult.update_forward_refs()
WtSite.CopyPagesParam.update_forward_refs()
WtSite.UploadPageParam.update_forward_refs()
WtSite.GetPageResult.update_forward_refs()
WtSite.CreatePagePackageParam.update_forward_refs()
WtSite.UploadPagePackageParam.update_forward_refs()
WtSite.ReadPagePackageResult.update_forward_refs()
