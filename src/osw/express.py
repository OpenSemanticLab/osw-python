# flake8: noqa: E402
"""
This module provides convenience functions for osw-python.
"""

import importlib.util
import re
from io import TextIOWrapper
from pathlib import Path
from uuid import uuid4
from warnings import warn

from typing_extensions import (
    IO,
    TYPE_CHECKING,
    Any,
    AnyStr,
    Buffer,
    Dict,
    List,
    Optional,
    TextIO,
    Union,
)

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.core import OSW, OVERWRITE_CLASS_OPTIONS, OverwriteOptions
from osw.defaults import params as default_params
from osw.defaults import paths as default_paths
from osw.model.static import OswBaseModel
from osw.utils.wiki import namespace_from_full_title, title_from_full_title
from osw.wtsite import WtSite

# Definition of constants
DEPENDENCIES = {
    # "Entity": "Category:Entity",  # depends on nothing#
    "Category": "Category:Category",  # depends on Entity
    "Property": "Category:Property",  # depends on Entity
    # "Item": "Category:Item",  # depends on Entity
    "Characteristics": "Category:OSW93ccae36243542ceac6c951450a81d47",  # depends on Item
    # "Data": "Category:OSW2ac4493f8635481eaf1db961b63c8325", # depends on Item
    # "File": "Category:OSWff333fd349af4f65a69100405a9e60c7",  # depends on Data
    "LocalFile": "Category:OSW3e3f5dd4f71842fbb8f270e511af8031",  # depends on File
    # "RemoteFile": "Category:OSW05b244d0a669436e96fe4e1631d5a171",  # depends on File
    "WikiFile": "Category:OSW11a53cdfbdc24524bf8ac435cbf65d9d",  # depends on RemoteFile
}


class OswExpress(OSW):
    """
    This class provides convenience functions for osw-python.
    """

    domain: str
    """The domain of the OSL instance to connect to."""
    cred_filepath: Optional[Union[str, Path]]
    """The filepath to the credentials file. Will be overwritten by the cred_filepath
    of cred_mngr, if it posses a non-None value. If cred_filepath is None,
    a default value is set."""
    cred_mngr: Optional[CredentialManager]
    """A credential manager object."""

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        domain: str,
        cred_filepath: Union[str, Path] = None,
        cred_mngr: CredentialManager = None,
    ):
        if cred_filepath is None:
            # Set default
            cred_filepath = default_paths.cred_filepath
            if cred_mngr is not None:
                if cred_mngr.cred_filepath is not None:
                    # But overwrite if the cred_mngr has a cred_filepath
                    cred_filepath = cred_mngr.cred_filepath[0]
        if not isinstance(cred_filepath, Path):
            cred_filepath = Path(cred_filepath)
        if cred_mngr is None:
            # Create a credentials manager
            if cred_filepath is None:
                cred_mngr = CredentialManager()
            else:  # Reuse passed cred_filepath
                cred_mngr = CredentialManager(cred_filepath=cred_filepath)
        if not cred_mngr.iri_in_file(domain):
            cred = cred_mngr.get_credential(
                CredentialManager.CredentialConfig(
                    iri=domain,
                    fallback=CredentialManager.CredentialFallback.ask,
                )
            )
            cred_mngr.add_credential(cred)
            # If there was no cred_filepath specified within the CredentialManager
            #  the filepath from the OswExpress constructor will be used (either passed
            #  as argument or set by default)
            if cred_mngr.cred_filepath is None:
                cred_mngr.save_credentials_to_file(
                    filepath=cred_filepath, set_cred_filepath=True
                )
            # If there was a cred_filepath specified within the CredentialManager,
            #  that filepath will be used
            else:
                cred_mngr.save_credentials_to_file()

        site = WtSite(WtSite.WtSiteConfig(iri=domain, cred_mngr=cred_mngr))
        super().__init__(**{"site": site, "domain": domain})
        self.cred_mngr = cred_mngr
        self.cred_filepath = cred_filepath

    def __enter__(self):
        """Return self when entering the context manager."""
        return self

    def __exit__(self):
        """Close the connection to the OSL instance when exiting the context manager."""
        self.close_connection()

    def close_connection(self):
        """Close the connection to the OSL instance."""
        self.mw_site.connection.close()

    def shut_down(self):
        """Makes sure this OSL instance can't be reused after it was shut down,
        as the connection can't be reopened except when initializing a new instance."""
        self.close_connection()
        del self

    def install_dependencies(
        self,
        dependencies: Dict[str, str] = None,
        mode: str = "append",
        policy: str = "force",
    ):
        """Installs data models, listed in the dependencies, in the osw.model.entity
        module.

        Parameters
        ----------
        dependencies
            A dictionary with the keys being the names of the dependencies and the
            values being the full page name (IRI) of the dependencies.
        mode
            The mode to use when loading the dependencies. Default is 'append',
            which will keep existing data models and only load the missing ones. The
            mode 'replace' will replace all existing data models with the new ones.
        policy
            The policy to use when loading the dependencies. Default is 'force',
            which will always load the dependencies. If policy is 'if-missing',
            dependencies will only be loaded if they are not already installed.
            This may lead to outdated dependencies, if the dependencies have been
            updated on the server. If policy is 'if-outdated', dependencies will only
            be loaded if they were updated on the server. (not implemented yet)
        """
        if dependencies is None:
            dependencies = DEPENDENCIES
        schema_fpts = []
        for k, v in dependencies.items():
            if policy != "if-missing" or not hasattr(model, k):
                schema_fpts.append(v)
            if policy == "if-outdated":
                raise NotImplementedError(
                    "The policy 'if-outdated' is not implemented yet."
                )
        schema_fpts = list(set(schema_fpts))
        for schema_fpt in schema_fpts:
            if not schema_fpt.count(":") == 1:
                raise ValueError(
                    f"Full page title '{schema_fpt}' does not have the correct format. "
                    "It should be 'Namespace:Name'."
                )
        self.fetch_schema(OSW.FetchSchemaParam(schema_title=schema_fpts, mode=mode))

    @staticmethod
    def check_dependencies(dependencies: Dict[str, str]) -> List[str]:
        """Check if the dependencies are installed in the osw.model.entity module.

        Parameters
        ----------
        dependencies
            A dictionary with the keys being the names of the dependencies and the
            values being the full page name (IRI) of the dependencies.
        """
        return [dep for dep in dependencies if not hasattr(model, dep)]

    def ensure_dependencies(self, dependencies: Dict[str, str]):
        """Ensure that the dependencies are installed in the osw.model.entity module.

        Parameters
        ----------
        dependencies
            A dictionary with the keys being the names of the dependencies and the
            values being the full page name (IRI) of the dependencies.
        """
        if self.check_dependencies(dependencies):
            self.install_dependencies(dependencies)

    def download_file(
        self,
        url_or_title: str,
        mode: str = "r",
        delete_after_use: bool = False,
        target_dir: Optional[Union[str, Path]] = None,
        target_fn: Optional[str] = None,
        target_fp: Optional[Union[str, Path]] = None,
        overwrite: bool = False,
        use_cached: bool = False,
    ) -> "DownloadFileResult":
        """Download a file from a URL to a target directory.

        Parameters
        ----------
        url_or_title
            The URL or full page title of the WikiFile page to download.
        mode
            The mode to open the file in. Default is 'r'. Implements the built-in open.
        delete_after_use
            If True, the file will be deleted after use.
        target_dir
            The target directory to download the file to. If None, the current working
            will be used.
        target_fn
            The target filename to save the file as. If None, the filename will be taken
            from the URL or title.
        target_fp
            The target filepath to save the file to. If None, the file will be saved to
            the target directory with the target filename.
        overwrite
            If True, the file will be overwritten if it already exists. If False, the
            file
            will not be downloaded if it already exists.
        use_cached
            If True, the file will be reloaded from the cache. If False, the file will
            be reloaded from the server. This option is useful if you are debugging
            code and don't want to reload the file from the server every time.

        Returns
        -------
        result
            A specific result object.
        """
        return DownloadFileResult(
            url_or_title=url_or_title,
            mode=mode,
            delete_after_use=delete_after_use,
            target_dir=target_dir,
            target_fn=target_fn,
            target_fp=target_fp,
            osw_express=self,
            overwrite=overwrite,
            use_cached=use_cached,
        )

    def upload_file(
        self,
        source: Union["LocalFileController", "WikiFileController", str, Path],
        url_or_title: Optional[str] = None,
        overwrite: OVERWRITE_CLASS_OPTIONS = OverwriteOptions.true,
        delete_after_use: bool = False,
        label: Optional[List[model.Label]] = None,
        name: Optional[str] = None,
        description: Optional[List[model.Description]] = None,
        change_id: Optional[str] = None,
        **properties: Dict[str, Any],
    ) -> "UploadFileResult":
        """Upload a file to an OSL page.

        Parameters
        ----------
        source
            The source file to upload. Can be a LocalFileController, WikiFileController,
            str or Path.
        url_or_title
            The URL or full page title of the WikiFile page to upload the file to. Used to
            overwrite autogenerated full page title on the target domain. If it is
            included, the domain can be parsed from the URL.
        overwrite
            If True, the file will be overwritten if it already exists. If False, the file
            will not be downloaded if it already exists.
        delete_after_use
            If True, the file will be deleted after use.
        label
            The labels to set on the WikiFile data model prior to uploading it to the OSL
            instance. The labels will end up in the JSON data slot of the to be created
            WikiFile page.
        name
            The name of the file. If None, the name will be taken from the source file.
        description
            The description to set on the WikiFile data model prior to uploading it to the
            OSL instance.
        change_id
            The id of the change to use for the upload. If None, a new change id will be
            generated.
        properties
            The properties to set on the WikiFile data model prior to uploading it to
            the OSL instance. Properties listed here, won't overwrite properties handed
            over in this function call, e.g., labe, name, description.
            Properties will end up in the JSON data slot of the to be created WikiFile
            page, if they match the WikiFile data model.

        Returns
        -------
        result
            A specific result object.
        """
        # Preparing all args, kwargs & properties to set for the uploaded file
        data = {**locals(), **properties}
        # Clean data dict to avoid passing None values
        data = {key: value for key, value in data.items() if value is not None}
        # Make sure self is passed as osw_express
        data["osw_express"] = self
        # Initialize the UploadFileResult object
        return UploadFileResult(source=source, **data)


try:
    # To load the dependencies that are not part of the osw.model.entity module as
    # uploaded to the repository
    from osw.controller.file.base import FileController  # depends on File
    from osw.controller.file.local import LocalFileController  # depends on LocalFile
    from osw.controller.file.memory import InMemoryController  # depends on LocalFile
    from osw.controller.file.wiki import WikiFileController  # depends on WikiFile
except AttributeError as e:
    warn(
        f'An exception occurred while loading the module dependencies: \n"{e}"'
        "A connection to an OSW instance, to fetch the dependencies from, has to be "
        "established!"
    )
    # If the default was not changed, make sure the user is prompted to enter the domain
    if default_params.has_changed("wiki_domain"):
        domain_ = default_params.wiki_domain
    else:
        domain_ = input("Please enter the domain of the OSW instance to connect to:")
        if domain_ == "":
            domain_ = default_params.wiki_domain
    if default_paths.has_changed("cred_filepath"):
        osw_express_ = OswExpress(
            domain=domain_, cred_filepath=default_paths.cred_filepath
        )
    else:
        osw_express_ = OswExpress(domain=domain_)
    osw_express_.install_dependencies(DEPENDENCIES)
    osw_express_.shut_down()  # Avoiding connection error
    print(
        "Dependencies specified in the module 'osw.express' have been fetched from "
        "OSW."
    )
    # Try again
    from osw.controller.file.base import FileController  # depends on File
    from osw.controller.file.local import LocalFileController  # depends on LocalFile
    from osw.controller.file.memory import InMemoryController  # depends on LocalFile
    from osw.controller.file.wiki import WikiFileController  # depends on WikiFile


class FileResult(OswBaseModel):
    url_or_title: Optional[str] = None
    """The URL or full page title of the WikiFile page."""
    file_io: Optional[Union[TextIO, TextIOWrapper, None]] = None
    """The file object. They type depends on the file type."""
    mode: str = "r"
    """The mode to open the file in. Default is 'r'. Implements the built-in open."""
    delete_after_use: bool = False
    """If True, the file will be deleted after use."""
    path: Optional[Path] = None
    """Overwriting the attribute of the base class to avoid validation error at
    initialization. The path to the file."""
    osw_express: Optional[OswExpress] = None
    """An OswExpress object. If None, a new OswExpress object will be created using
    the credentials_manager or domain and cred_filepath."""
    domain: Optional[str] = None
    """The domain of the OSL instance to download the file from. Required if
    urL_or_title is a full page title. If None the domain is parsed from the URL."""
    cred_filepath: Optional[Union[str, Path]] = None
    """The filepath to the credentials file. Will only be used if cred_mngr is
    None. If cred_filepath is None, a credentials file named 'accounts.pwd.yaml' is
    expected to be found in the current working directory.
    """
    cred_mngr: Optional[CredentialManager] = None
    """A credential manager object. If None, a new credential manager will be created
    using the cred_filepath."""

    class Config:
        arbitrary_types_allowed = True

    def open(self, mode: str = None, **kwargs) -> TextIO:
        """Open the file, if not already opened using the 'mode' argument (priority) or
        the 'mode' attribute."""
        if mode is None:
            mode = self.mode
        kwargs["mode"] = mode
        if self.file_io is None or self.file_io.closed:
            self.file_io = open(self.path, **kwargs)
        return self.file_io

    def close(self) -> None:
        """Close the file, if not already closed."""
        if self.file_io is None or self.file_io.closed:
            warn("File already closed or not opened.")
        else:
            self.file_io.close()

    def read(self, n: int = -1) -> AnyStr:
        """Read the file. If n is not specified, the entire file will be read.
        If the file is not already opened, it will be opened."""
        if self.file_io is None or self.file_io.closed:
            self.file_io = self.open(mode="r")
        return self.file_io.read(n)

    def write(self, s: Union[Buffer, AnyStr]):
        """Write to the file. If the file is not already opened, it will be opened."""
        if self.file_io is None or self.file_io.closed:
            self.file_io = self.open(mode="w")
        return self.file_io.write(s)

    def __enter__(self):
        """Open the file when entering the context manager."""
        if self.file_io is None or self.file_io.closed:
            self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Close the file when exiting the context manager, and deletes the file if
        'delete_after_use' was set."""
        self.close()
        if self.delete_after_use and self.path.exists():
            self.path.unlink()

    def process_init_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Get the field default values (attribute defaults)
        attr_def_vals = {
            field_name: field.default
            for field_name, field in self.__class__.__fields__.items()
        }
        # Set the default values for the attributes, if no value was passed
        for key, value in attr_def_vals.items():
            if data.get(key) is None:
                data[key] = value
        # Do replacements
        if (
            data.get("label") == InMemoryController.__fields__["label"].get_default()
            or data.get("label")
            == LocalFileController.__fields__["label"].get_default()
            or data.get("label") == WikiFileController.__fields__["label"].get_default()
        ):
            # Make sure that the label is not set to the default value, it will be
            # set by the source file controller
            del data["label"]
        if data.get("cred_filepath") is None:
            data["cred_filepath"] = default_paths.cred_filepath
        if not data.get("cred_filepath").parent.exists():
            data["cred_filepath"].parent.mkdir(parents=True)
        if data.get("cred_mngr") is None:
            data["cred_mngr"] = CredentialManager()
            if data.get("cred_filepath").exists():
                data["cred_mngr"] = CredentialManager(
                    cred_filepath=data.get("cred_filepath")
                )
        return data


class DownloadFileResult(FileResult, LocalFileController):
    """A specific result object to describe the result of downloading a file from an
    OSL instance."""

    url_or_title: str
    """The URL or full page title of the WikiFile page to download the file from."""
    target_dir: Optional[Union[str, Path]] = None
    """The target directory to download the file to. If None, the current working
    will be used."""
    target_fn: Optional[str] = None
    """The target filename to save the file as. If None, the filename will be taken
    from the URL or title."""
    target_fp: Optional[Union[str, Path]] = None
    """The target filepath to save the file to. If None, the file will be saved to the
    target directory with the target filename."""
    overwrite: bool = False
    """If True, the file will be overwritten if it already exists. If False, the file
    will not be downloaded if it already exists."""
    use_cached: bool = False
    """If True, the file will be reloaded from the cache. If False, the file will be
    reloaded from the server. This option is useful if you are debugging code and
    don't want to reload the file from the server every time."""

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, url_or_title, **data):
        """The constructor for the context manager."""
        # Note: in pydantic v2 we can use
        # https://docs.pydantic.dev/latest/api/base_model/#pydantic.BaseModel.model_post_init

        data["url_or_title"] = url_or_title
        # Do replacements
        data = self.process_init_data(data)
        if data.get("target_fn") is None:
            data["target_fn"] = url_or_title.split("File:")[-1]
        if data.get("target_dir") is None:
            data["target_dir"] = default_paths.download_dir
        if isinstance(data.get("target_dir"), str):
            data["target_dir"] = Path(data.get("target_dir"))
        if data.get("target_fp") is None:
            data["target_fp"] = data.get("target_dir") / data.get("target_fn")
        # Setting path after all operations on target_fp are complete
        data["path"] = data.get("target_fp")
        if data.get("domain") is None:
            match = re.search(
                pattern=r"(?:(?:https?:\/\/)?(?:www\.)?([^\/]+))\/wiki",
                string=url_or_title,
            )
            if match is None:
                raise ValueError(
                    f"Could not parse domain from URL: {url_or_title}. "
                    f"Either specify URL or domain and full page title."
                )
            data["domain"] = match.group(1)
        if data.get("use_cached") and data.get("target_fp").exists():
            # Here, no file needs to be downloaded, but self need to be initialized
            #  with the path to the file
            # Clean data dict to avoid passing None values
            data = {key: value for key, value in data.items() if value is not None}
            super().__init__(**data)  # data includes "path"
        else:
            if data.get("osw_express") is None:
                data["osw_express"] = OswExpress(
                    domain=data.get("domain"),
                    cred_mngr=data.get("cred_mngr"),
                )
            title: str = "File:" + url_or_title.split("File:")[-1]
            file = data.get("osw_express").load_entity(title)
            wf: WikiFileController = file.cast(
                WikiFileController, osw=data.get("osw_express")
            )
            """The file controller"""
            if data.get("target_fp").exists() and not data.get("overwrite"):
                raise FileExistsError(
                    f"File already exists: {data.get('target_fp')}. Set "
                    f"overwrite_existing=True to overwrite."
                )
            if not data.get("target_fp").parent.exists():
                data.get("target_fp").parent.mkdir(parents=True)
            lf = LocalFileController.from_other(wf, path=data.get("target_fp"))
            # Clean data dict to avoid passing None values
            data = {key: value for key, value in data.items() if value is not None}
            super().__init__(**{**lf.dict(), **data})
            self.put_from(wf)
        # File is only opened at request to avoid locking the file


def osw_download_file(
    url_or_title: str,
    mode: str = "r",
    delete_after_use: bool = False,
    target_dir: Optional[Union[str, Path]] = None,
    target_fn: Optional[str] = None,
    target_fp: Optional[Union[str, Path]] = None,
    osw_express: Optional[OswExpress] = None,
    domain: Optional[str] = None,
    cred_filepath: Optional[Union[str, Path]] = None,
    cred_mngr: Optional[CredentialManager] = None,
    overwrite: bool = False,
    use_cached: bool = False,
) -> DownloadFileResult:
    """Download a file from a URL to a target directory.

    Parameters
    ----------
    url_or_title
        The URL or full page title of the WikiFile page to download.
    mode
        The mode to open the file in. Default is 'r'. Implements the built-in open.
    delete_after_use
        If True, the file will be deleted after use.
    target_dir
        The target directory to download the file to. If None, the current working
        will be used.
    target_fn
        The target filename to save the file as. If None, the filename will be taken
        from the URL or title.
    target_fp
        The target filepath to save the file to. If None, the file will be saved to the
        target directory with the target filename.
    osw_express
        An OswExpress object. If None, a new OswExpress object will be created using
        the credentials_manager or domain and cred_filepath.
    domain
        The domain of the OSL instance to download the file from. Required if
        urL_or_title is a full page title. If None the domain is parsed from the URL.
    cred_filepath
        The filepath to the credentials file. Will only be used if cred_mngr is
         None. If cred_filepath is None, a credentials file named 'accounts.pwd.yaml'
         is expected to be found in the current working directory.
    cred_mngr
        A credential manager object. If None, a new credential manager will be created
        using the cred_filepath.
    overwrite
        If True, the file will be overwritten if it already exists. If False, the file
        will not be downloaded if it already exists.
    use_cached
        If True, the file will be reloaded from the cache. If False, the file will be
        reloaded from the server. This option is useful if you are debugging code and
        don't want to reload the file from the server every time.

    Returns
    -------
    result
        A specific result object.
    """
    return DownloadFileResult(
        url_or_title=url_or_title,
        mode=mode,
        delete_after_use=delete_after_use,
        target_dir=target_dir,
        target_fn=target_fn,
        target_fp=target_fp,
        osw_express=osw_express,
        domain=domain,
        cred_filepath=cred_filepath,
        cred_mngr=cred_mngr,
        overwrite=overwrite,
        use_cached=use_cached,
    )


class UploadFileResult(FileResult, WikiFileController):
    """A specific result object to describe the result of uploading a file to an
    OSL instance."""

    source: Union[LocalFileController, WikiFileController, str, Path, IO]
    """The source of the file to be uploaded."""
    url_or_title: Optional[str] = None
    """The URL or full page title of the WikiFile page to upload the file to. Used to
    overwrite autogenerated full page title on the target domain."""
    target_fpt: Optional[str] = None
    """The full page title of the WikiFile page to upload the file to. If None, the
    title will be taken from the URL or title."""
    source_file_controller: Optional[FileController] = None
    """The source file controller to upload the file from. Can be a LocalFileController
    or a WikiFileController."""
    overwrite: OVERWRITE_CLASS_OPTIONS = OverwriteOptions.true
    """If True, the file will be overwritten if it already exists. If False, the file
    will not be uploaded if it already exists. See osw.core for more information."""
    change_id: Optional[str] = None
    """The change ID of the WikiFile page to upload the file to, stored in the meta
    property."""

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        source: Union[LocalFileController, WikiFileController, str, Path, IO],
        **data: Dict[str, Any],
    ):
        # Do replacements on all data (including the those values taken from the
        # default values of the class definition)
        data = self.process_init_data(data)
        # If a source_file_controller was provided, the 'path' should already be set.
        if isinstance(source, LocalFileController) or isinstance(
            source, WikiFileController
        ):
            data["source_file_controller"] = source
            data["source"] = source
        elif isinstance(source, str) or isinstance(source, Path):
            if not Path(source).exists():
                raise FileNotFoundError(f"File not found: {source}")
            if Path(source).is_dir():
                raise IsADirectoryError(f"File expected. Path is a directory: {source}")
            # source is a path to a file that exists - might also be a file in the CWD
            data["path"] = Path(source)
            data["source"] = Path(source)
            data["source_file_controller"] = LocalFileController(path=data.get("path"))
        elif isinstance(source, IO):
            data["source_file_controller"] = InMemoryController(stream=source)
        else:
            raise ValueError(
                "The 'source' argument must be a LocalFileController, WikiFileController,"
                " str, Path or IO object."
            )
        # If url_or_title is given, it either
        # * contains a valid domain, which can be used in osw_express
        # * contains a full page title, which is the target page
        if data.get("url_or_title") is not None:
            # Check right format of the title
            if "File:" not in data.get("url_or_title"):
                raise ValueError(
                    "The 'url_or_title' should contain the namespace 'File'."
                    f"'{data.get('url_or_title')}' does not."
                )
            # Get the full page title from the URL or title
            fpt = "File:" + data.get("url_or_title").split("File:")[-1]
            if data.get("target_fpt") is None:
                data["target_fpt"] = fpt
            else:
                if not data.get("target_fpt") == fpt:
                    raise ValueError(
                        "The full page title specified in 'url_or_title' does not "
                        "match the full page title specified in 'target_fpt'."
                    )
            # Get the domain from the URL or title
            match = re.search(
                pattern=r"(?:(?:https?:\/\/)?(?:www\.)?([^\/]+))\/wiki",
                string=data.get("url_or_title"),
            )
            if data.get("domain") is None:
                if match is not None:
                    data["domain"] = match.group(1)
            else:
                if match is not None:
                    if not data.get("domain") == match.group(1):
                        raise ValueError(
                            "The domain specified in 'url_or_title' does not match the "
                            "domain specified in 'domain'."
                        )
            # If the full page title is given, the domain must be given as well or
            # osw_express must be given
            if data.get("domain") is None and data.get("osw_express") is None:
                raise ValueError(
                    "If 'url_or_title' is a full page title, 'domain' or "
                    "'osw_express' must be specified."
                )
        # Create an osw_express object if not given
        if data.get("osw_express") is None:
            create_new = True
            # Try to get the osw_express object from the source_file_controller
            if data.get("source_file_controller") is not None:
                if hasattr(data["source_file_controller"], "osw_express"):
                    create_new = False
                    data["osw_express"] = data["source_file_controller"].osw_express
            # Otherwise create a new osw_express object
            if create_new:
                data["osw_express"] = OswExpress(
                    domain=data.get("domain"),
                    cred_mngr=data.get("cred_mngr"),
                )
        # If no change_id is given, generate a new one
        if data.get("change_id") is None:
            data["change_id"] = str(uuid4())
        # Change_id will be returned in the UploadFileResult.change_id attribute
        # If given set titel and namespace
        if data.get("target_fpt") is not None:
            namespace = namespace_from_full_title(data.get("target_fpt"))
            title = title_from_full_title(data.get("target_fpt"))
            wiki_page = model.WikiPage(namespace=namespace, title=title)
            data["meta"] = model.Meta(wiki_page=wiki_page)
            data["title"] = title
        # Set change_id to existing meta
        for meta in [data.get("meta"), getattr(data["source_file_controller"], "meta")]:
            if meta is not None:
                if getattr(meta, "change_id", None) is None:
                    meta.change_id = [data["change_id"]]
                else:
                    meta.change_id.append(data.get("change_id"))
        # Clean data dict
        data = {key: value for key, value in data.items() if value is not None}
        # Create the WikiFileController from the source_file_controller
        wfc = WikiFileController.from_other(
            other=data.get("source_file_controller"),
            osw=data.get("osw_express"),
            **data,
            # Passes arguments to the cast() method, e.g., overwrite the label
            #  cast method will call init
        )
        # Upload to the target OSW instance
        wfc.put_from(data.get("source_file_controller"), **data)
        data["url_or_title"] = wfc.url
        super().__init__(**{**wfc.dict(), **data})
        # Don't open the local (uploaded) file


def osw_upload_file(
    source: Union[LocalFileController, WikiFileController, str, Path],
    url_or_title: Optional[str] = None,
    overwrite: OVERWRITE_CLASS_OPTIONS = OverwriteOptions.true,
    delete_after_use: bool = False,
    osw_express: Optional[OswExpress] = None,
    domain: str = None,
    cred_filepath: Optional[Union[str, Path]] = None,
    cred_mngr: Optional[CredentialManager] = None,
    label: Optional[List[model.Label]] = None,
    name: Optional[str] = None,
    description: Optional[List[model.Description]] = None,
    change_id: Optional[str] = None,
    **properties: Dict[str, Any],
) -> UploadFileResult:
    """Upload a file to an OSL page.

    Parameters
    ----------
    source
        The source file to upload. Can be a LocalFileController, WikiFileController,
        str or Path.
    url_or_title
        The URL or full page title of the WikiFile page to upload the file to. Used to
        overwrite autogenerated full page title on the target domain. If it is
        included, the domain can be parsed from the URL.
    overwrite
        If True, the file will be overwritten if it already exists. If False, the file
        will not be downloaded if it already exists.
    delete_after_use
        If True, the file will be deleted after use.
    osw_express
        An OswExpress object. If None, a new OswExpress object will be created using
        the credentials_manager, or domain and cred_filepath.
    domain
        The domain of the OSL instance to upload the file to. Required if no
        OswExpress was pass to osw_express. If None the domain can be parsed from
        the URL. If fpt_or_url is no URL user must specify the domain.
    cred_filepath
        The filepath to the credentials file. Will only be used if cred_mngr is
         None. If cred_filepath is None, a credentials file named 'accounts.pwd.yaml'
         is expected to be found in the current working directory.
    cred_mngr
        A credential manager object. If None, a new credential manager will be created
        using the cred_filepath.
    label
        The labels to set on the WikiFile data model prior to uploading it to the OSL
        instance. The labels will end up in the JSON data slot of the to be created
        WikiFile page.
    name
        The name of the file. If None, the name will be taken from the source file.
    description
        The description to set on the WikiFile data model prior to uploading it to the
        OSL instance.
    change_id
        The change ID of the WikiFile page to upload the file to, stored in the meta
        property.
    properties
        The properties to set on the WikiFile data model prior to uploading it to
        the OSL instance. Properties listed here, won't overwrite properties handed
        over in this function call, e.g., labe, name, description.
        Properties will end up in the JSON data slot of the to be created WikiFile
        page, if they match the WikiFile data model.

    Returns
    -------
    result
        A specific result object.
    """
    # Preparing all args, kwargs & properties to set for the uploaded file
    data = {**locals(), **properties}
    # Clean data dict to avoid passing None values
    data = {key: value for key, value in data.items() if value is not None}
    # Initialize the UploadFileResult object
    return UploadFileResult(**data)


class DataModel(OswBaseModel):
    module: str
    """The full address of the module to import from, e.g., 'osw.model.entity'."""
    class_name: str
    """The target class name to import, e.g., 'Entity' in 'from osw.model.entity
    import Entity'."""
    osw_fpt: str = None
    """Full page title of the data model in an OSL instance to be fetched if not
    already available in osw.model.entity, e.g., 'Category:Entity'."""


def import_with_fallback(
    to_import: Union[List[DataModel], Dict[str, str]],
    caller_globals: dict,
    module: str = None,
    dependencies: Dict[str, str] = None,
    domain: str = None,
    cred_filepath: Union[str, Path] = None,
    osw_express: OswExpress = None,
):
    """Imports data models with a fallback to fetch the dependencies from an OSL
    instance if the data models are not available in the local osw.model.entity module.

    DISCLAIMER: Will prompt the user to enter domain and credentials if no domain and
    cred_filepath or osw_express was passed.

    BEST USAGE: See examples, for best usage in a script to be rerun multiple times
    (without refetching datamodels).

    Parameters
    ----------
    to_import
        List of DataModel objects or a dictionary, with (key: value) pairs (class_name:
        osw_fpt) to import.
    caller_globals
        (Mandatory!) The globals dictionary as returned by globals() in the calling
        script.
    module
        (Optional) The module to import the data models from. Used only if to_import
        is of type List[Dict]. Defaults to 'osw.model.entity' if not specified.
    dependencies
        A dictionary with the keys being the names of the dependencies and the values
        being the full page name of the dependencies.
    domain
        The domain of the OSL instance to connect to, if the dependencies are not
        available in the local osw.model.entity module.
    cred_filepath
        The filepath to the credentials file. If None, a credentials file is created
        under the default path.
    osw_express
        An OswExpress object. If None, a new OswExpress object will be created using
        the credentials_manager or domain and cred_filepath.

    Examples
    --------
    >>> from pathlib import Path
    >>> from osw.defaults import paths, params
    >>> from osw.express import import_with_fallback, DataModel, OswExpress
    >>> wiki_domain__ = "wiki-dev.open-semantic-lab.org"
    >>> cred_filepath__ = Path(r"accounts.pwd.yaml")
    >>> osw_obj = OswExpress(domain=wiki_domain__, cred_filepath=cred_filepath__)
    >>> import_with_fallback(
    >>>     [DataModel(module="osw.controller.file.base",class_name="FileController")],
    >>>     globals(), osw_express=osw_obj
    >>> )

    Returns
    -------
    None
    """
    if isinstance(to_import, dict):
        # The arg 'to_import' should have the right structure to act as 'dependencies'
        # Assume all DataModels are part of osw.model.entity
        if module is None:
            module = "osw.model.entity"
        # A list of DataModels will be derived from the dict
        to_import = [
            DataModel(
                module=module,
                class_name=key,
                osw_fpt=value,
            )
            for key, value in to_import.items()
        ]
    if to_import is None:
        raise ValueError(
            "Either the argument 'to_import' or 'dependencies' must be passed to the "
            "function import_with_fallback()."
        )
    try:
        # Try to import the listed data models from the (listed) module(s)
        for ti in to_import:
            # Raises AttributeError if the target could not be found
            caller_globals[ti.class_name] = getattr(
                importlib.import_module(ti.module), ti.class_name
            )
    except Exception as e:
        if dependencies is None:
            dependencies = {}
            warn(
                "No 'dependencies' were passed to the function "
                "import_with_fallback()! Trying to derive them from 'to_import'."
            )
        new_dependencies = {
            module.class_name: module.osw_fpt
            for module in to_import
            if module.osw_fpt is not None
        }
        dependencies.update(new_dependencies)
        if not dependencies:
            raise AttributeError(
                f"An exception occurred while loading the module dependencies: \n"
                f'"{e}"\n'
                "No 'dependencies' were passed to the function import_with_fallback() "
                "and could not be derived from 'to_import'!"
            )
        warn(
            f'An exception occurred while loading the module dependencies: \n"'
            f'{e}"\n'
            "A connection to an OSW instance, to fetch the dependencies from, "
            "has to be established!"
        )
        # todo: should  this be taken from globals?
        # If the user has set the default domain, use it
        if domain is None:
            if default_params.has_changed("wiki_domain"):
                domain = default_params.wiki_domain
            else:
                domain = input(
                    "Please enter the domain of the OSW instance to connect to:"
                )
                if domain == "":
                    domain = default_params.wiki_domain
        if cred_filepath is None:
            cred_filepath = default_paths.cred_filepath
        if osw_express is None:
            osw_express = OswExpress(domain=domain, cred_filepath=cred_filepath)

        osw_express.install_dependencies(dependencies, mode="append")
        osw_express.shut_down()  # Avoiding connection error
        # Try again to import the data models
        for ti in to_import:
            # Raises AttributeError if the target could not be found
            caller_globals[ti.class_name] = getattr(
                importlib.import_module(ti.module), ti.class_name
            )


OswExpress.update_forward_refs()

# todo:
#  * create a .gitignore in the basepath that lists the default credentials file (
#  accounts.pwd.yaml) OR append to an existing .gitignore#

# todo:
#  Ideas:
#  * New express function:
#    * Move gui.save_as_page_package and wrap in osw.express
#    * parallel download of multiple files
#    * query all instances of a category (direct members or member of subcategories
#      as well = crawl)
#    * Get query results into a pandas.DataFrame
#    * upload any file to wiki whilst specifying the page to attach it to + select a
#      property to link it to [basic example at file_upload_download.py]
#      inputs:
#           source:Union[LocalFileController, WikiFileController, str, Path],
#           target_fpt_or_uri: Optional[str]
#           properties / Links: Optional[str]
#           commit message
#      * Save a pandas.DataFrame to a WikiFile (as table, e.g. as csv, xlsx,
#        json)
#    * Save a wiki page as pdf
