"""
This module provides convenience functions for osw-python.
"""

import os
import re
from contextlib import contextmanager
from pathlib import Path
from warnings import warn

import yaml
from typing_extensions import Optional, Union

from osw.auth import CredentialManager
from osw.controller.file.local import LocalFileController
from osw.controller.file.wiki import WikiFileController
from osw.core import OSW
from osw.model.static import OswBaseModel
from osw.wtsite import WtSite

CREDENTIALS_FP_DEFAULT = Path(os.getcwd()) / "accounts.pwd.yaml"


class CredentialsFpDefault(OswBaseModel):
    """A class to store the default credentials filepath. This is a helper class to
    make the default credentials file path, defined within this module, accessible
    from a calling script."""

    default: Union[str, Path] = CREDENTIALS_FP_DEFAULT

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, str_or_path: Union[str, Path] = CREDENTIALS_FP_DEFAULT):
        super().__init__(default=str_or_path)
        self.default = Path(str_or_path)

    def __str__(self):
        return str(self.default)

    def __repr__(self):
        return f"CredentialsFpDefault(str_or_path={self.default})"

    def __eq__(self, other):
        if isinstance(other, CredentialsFpDefault):
            return self.default == other.default
        return False

    @property
    def path(self):
        return Path(self.default)

    def set_default(self, new: Union[str, Path]):
        self.default = new

    def get_default(self):
        return self.default


credentials_fp_default = CredentialsFpDefault()


def save_credential(cred: CredentialManager.BaseCredential, cred_fp: Union[str, Path]):
    """Save a credential to a file. Deprecated - delete in a future commit."""
    if isinstance(cred_fp, str):
        cred_fp = Path(cred_fp)
    data = {}
    if cred_fp.exists():
        with open(cred_fp, "r") as f:
            data = yaml.safe_load(f)
    cred_dict = cred.dict()
    if "iri" in cred_dict:
        del cred_dict["iri"]
    data[cred.iri] = cred_dict
    with open(cred_fp, "w") as f:
        yaml.dump(data, f)


class OswExpress(OSW):
    """
    This class provides convenience functions for osw-python.
    """

    domain: str
    """The domain of the wiki to connect to."""
    cred_fp: Optional[Union[str, Path]]
    """The filepath to the credentials file."""
    credential_manager: Optional[CredentialManager]
    """A credential manager object."""

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        domain: str,
        cred_fp: Union[str, Path] = None,
        credential_manager: CredentialManager = None,
    ):
        if cred_fp is None:
            cred_fp = credentials_fp_default.get_default()
        if isinstance(cred_fp, str):
            cred_fp = Path(cred_fp)
        if credential_manager is None:
            if cred_fp.exists():
                credential_manager = CredentialManager(cred_filepath=cred_fp)
                # todo: It would be expected that the credential_manager loads all
                #  credentials from the file to ._credentials, but it doesn't. This
                #  only happens on demand. Is this intended?
            else:
                credential_manager = CredentialManager()
        if not credential_manager.iri_in_file(domain):
            cred = credential_manager.get_credential(
                CredentialManager.CredentialConfig(
                    iri=domain,
                    fallback=CredentialManager.CredentialFallback.ask,
                )
            )
            credential_manager.add_credential(cred)
            # If there was no cred_filepath specified within the CredentialManager
            #  the filepath from the OswExpress constructor will be used (either passed
            #  as argument or set by default)
            if credential_manager.cred_filepath is None:
                credential_manager.save_credentials_to_file(filepath=cred_fp)
            # If there was a cred_filepath specified within the CredentialManager,
            #  that filepath will be used
            else:
                credential_manager.save_credentials_to_file()
            warn(
                f"Credentials file created at '{credential_manager.cred_filepath}'."
                f" Remember to exclude this file from any commits by listing it in"
                f" .gitignore!"
            )

        site = WtSite(WtSite.WtSiteConfig(iri=domain, cred_mngr=credential_manager))
        super().__init__(**{"site": site, "domain": domain})
        self.credential_manager = credential_manager


class DownloadFileResult(LocalFileController):
    """
    A specific result object.
    """

    class Config:
        arbitrary_types_allowed = True

    def open(self, *args, mode: str = "r", **kwargs):
        return open(self.path, *args, mode=mode, **kwargs)


def osw_download_file(
    url_or_title: str,
    target_dir: Optional[Union[str, Path]] = None,
    target_fn: Optional[str] = None,
    target_fp: Optional[Union[str, Path]] = None,
    osw_express: Optional[OswExpress] = None,
    domain: Optional[str] = None,
    credentials_fp: Optional[Union[str, Path]] = None,
    credential_manager: Optional[CredentialManager] = None,
    overwrite: bool = False,
) -> DownloadFileResult:
    """Download a file from a URL to a target directory.

    Parameters
    ----------
    url_or_title
        The URL or full page title of the WikiFile page to download.
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
        the credentials_manager or domain and credentials_fp.
    domain
        The domain of the wiki to download the file from. Required if urL_or_title is
        a full page title. If None the domain is parsed from the URL.
    credentials_fp
        The filepath to the credentials file. Will only be used if credential_manager is
         None. If credentials_fp is None, a credentials file named 'accounts.pwd.yaml'
         is expected to be found in the current working directory.
    credential_manager
        A credential manager object. If None, a new credential manager will be created
        using the credentials_fp.
    overwrite
        If True, the file will be overwritten if it already exists. If False, the file
        will not be downloaded if it already exists.

    Returns
    -------
    result
        A specific result object.
    """
    cwd = Path(os.getcwd())
    if credentials_fp is None:
        credentials_fp = credentials_fp_default.get_default()
    if credential_manager is None:
        credential_manager = CredentialManager(cred_filepath=credentials_fp)
    if target_fn is None:
        target_fn = url_or_title.split("File:")[-1]
    if target_dir is None:
        target_dir = cwd
    if isinstance(target_dir, str):
        target_dir = Path(target_dir)
    if target_fp is None:
        target_fp = target_dir / target_fn
    if domain is None:
        match = re.search(
            pattern=r"(?:(?:https?:\/\/)?(?:www\.)?([^\/]+))\/wiki", string=url_or_title
        )
        if match is None:
            raise ValueError(
                f"Could not parse domain from URL: {url_or_title}. "
                f"Either specify URL or domain and full page title."
            )
        domain = match.group(1)
    if osw_express is None:
        osw_express = OswExpress(domain=domain, credential_manager=credential_manager)
    title = "File:" + url_or_title.split("File:")[-1]
    file = osw_express.load_entity(title)
    wf = file.cast(WikiFileController, osw=osw_express)  # the file controller
    if target_fp.exists() and not overwrite:
        raise FileExistsError(
            f"File already exists: {target_fp}. Set overwrite_existing=True to "
            f"overwrite."
        )
    lf = LocalFileController.from_other(wf, path=target_fp)
    lf.put_from(wf)
    return lf.cast(DownloadFileResult)


@contextmanager
def osw_open(
    url_or_title: str, *args, mode: str = "r", delete_after_use: bool = False, **kwargs
):
    """Context manager for downloading files with OswExpress.

    Parameters
    ----------
    url_or_title
        The URL or full page title of the WikiFile page to download.
    args
        Additional arguments to pass to open.
    mode
        The mode to open the file in. Default is 'r'.
    delete_after_use
        If True, the file will be deleted after use.
    kwargs
        Additional keyword arguments to pass to open.

    Yields
    ------
    file
        The file object.
    """

    local_file = osw_download_file(url_or_title, overwrite=True, **kwargs)
    file_path = local_file.path
    file = local_file.open(*args, mode=mode, **kwargs)
    try:
        yield file
    finally:
        file.close()
        if delete_after_use:
            file_path.unlink()


# todo:
#  * move necessary entity models to static.py / hardcode them into entity.py
#  * should be context manager compatible as:
#       with download_file(...) as file:
#           file.read()
#  * but should also be usable directly as:
#       file = download_file(...) -> should return a LocalFileController object
#  * see if an implementation as suggested by BingChat is feasible:
#       https://sl.bing.net/bJTlJvcyTv2
