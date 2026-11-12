import functools
import logging
import os
from typing import IO, Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import mwclient.errors
from oold.backend.auth import get_credential as _get_registered_credential
from oold.backend.auth import registered_credentials as _registered_credentials

from osw.auth import CredentialManager
from osw.controller.file.base import FileController
from osw.controller.file.remote import RemoteFileController
from osw.core import OSW, model
from osw.utils.wiki import get_namespace, get_title
from osw.wtsite import WtSite

_logger = logging.getLogger(__name__)


def format_allowed_extensions(allowed: WtSite.AllowedFileExtensionsResult) -> str:
    """Renders the allowed-extensions hint for a rejected-upload error message"""
    if not allowed.extensions or allowed.fetched_at is None:
        return ""
    ttl_hours = int(WtSite.ALLOWED_FILE_EXTENSIONS_TTL.total_seconds() // 3600)
    return (
        f" Extensions allowed there, read {allowed.fetched_at:%Y-%m-%d %H:%M:%S} and "
        f"cached for {ttl_hours} h: {', '.join(sorted(allowed.extensions))}. "
        "Call osw.site.clear_allowed_file_extensions_cache() to re-read the list "
        "if the wiki configuration changed since."
    )


def reraise_upload_error(
    error: mwclient.errors.APIError, site: WtSite, title: str, suffix: Optional[str]
) -> None:
    """Turns a rejected file extension into a readable error, re-raises the rest

    MediaWiki reports a rejected extension as filetype-banned,
    filetype-banned-type or filetype-badtype, depending on the version.
    """
    if "filetype" not in str(getattr(error, "code", "")):
        raise error
    allowed = site.get_allowed_file_extensions()
    hint = format_allowed_extensions(allowed)
    raise ValueError(
        f"Upload of '{title}' was rejected because the file extension "
        f"'{suffix}' is not allowed on {site.mw_site.host}.{hint}"
    ) from error


def assert_upload_success(result: Any, title: str, host: str) -> None:
    """Raises unless the upload API reports that it stored the file

    mwclient raises only when the response carries an 'error' key. A file that
    MediaWiki declined for any other reason comes back as a normal return value
    with a result other than 'Success', so without this check the upload would
    fail silently.
    """
    status = result.get("result") if isinstance(result, dict) else None
    if status == "Success":
        return
    warnings = result.get("warnings") if isinstance(result, dict) else None
    detail = f" Warnings: {warnings}." if warnings else ""
    raise ValueError(
        f"Upload of '{title}' to {host} did not succeed (result: {status}).{detail}"
    )


def store_params_for_upload(
    se_params: Dict[str, Any], page_existed: bool
) -> Dict[str, Any]:
    """Picks the overwrite policy for the entity that accompanies an upload

    An upload creates the file page when it was not there yet. store_entity
    would then see an existing page and, under the default 'keep existing',
    leave the metadata unwritten. So the entity has to replace what the upload
    put there. A page that was already there keeps whatever the caller asked
    for.
    """
    if page_existed:
        return se_params
    return {**se_params, "overwrite": "replace remote"}


_sessions: Dict[Tuple[str, str], Tuple[Any, OSW]] = {}
"""Sessions by (host, credential IRI), with the credential they were built from.

The credential is part of the key because two credentials scoped to different
paths of one wiki are two different logins; the host is, because one credential
can match several hosts - oold's lookup treats a stored IRI contained in the
searched one as a match, so a credential for ``example.org`` answers for every
subdomain. The credential itself is kept so a later ``set_credential`` replaces
the session instead of being ignored for the lifetime of the process.
"""


def clear_sessions() -> None:
    """Drop the cached sessions, so the next access logs in again."""
    _sessions.clear()


def host_of(url: str) -> str:
    """The wiki host a URL or a bare credential IRI names.

    A credential is registered under whatever its owner chose - a bare host, a
    host with a path, a full URL. ``WtSite`` wants the host alone: given a path
    it builds an API endpoint that does not exist.
    """
    parsed = urlparse(url if "//" in url else f"//{url}")
    return parsed.netloc or url.split("/")[0]


def credential_for(url: str) -> Any:
    """The credential registered for ``url``, or a readable error."""
    try:
        return _get_registered_credential(url)
    except ValueError as error:
        raise ValueError(
            f"No credential registered for {host_of(url)}. Pass osw= explicitly "
            "or register one with oold.backend.auth.set_credential."
        ) from error


def session_for(url: str) -> OSW:
    """An OSW session for the host of ``url``, from the registered credential.

    The file entity may be stored somewhere other than its bytes, so the
    lookup key is the URL the content lives at, not the entity's own IRI.
    """
    host = host_of(url)
    credential = credential_for(url)
    key = (host, credential.iri)
    cached = _sessions.get(key)
    if cached is not None and cached[0] == credential:
        return cached[1]
    cred_mngr = CredentialManager()
    cred_mngr.add_credential(credential)
    session = OSW(site=WtSite(WtSite.WtSiteConfig(iri=host, cred_mngr=cred_mngr)))
    _sessions[key] = (credential, session)
    return session


class WikiFileController(model.WikiFile, RemoteFileController):
    """File controller for wiki files"""

    label: Optional[List[model.Label]] = [model.Label(text="Unnamed file")]
    """the label of the file, defaults to 'Unnamed file'"""
    osw: Optional[OSW] = None
    """the OSW instance to connect with. Left unset, it is created on first
    use from the credential registered for download_url / access_url."""
    namespace: Optional[str] = "File"
    """the namespace of the file, defaults to 'File'"""
    title: Optional[str] = None
    """the title of the file, defaults to the auto-generated OSW-ID"""
    suffix: Optional[str] = None
    """the suffix of the file, defaults to the suffix of the title"""

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_other(
        cls,
        other: FileController,
        osw: Optional[OSW] = None,
        **kwargs: Dict[str, Any],
    ) -> "WikiFileController":
        # Only pass a session that was given: writing None over the one the
        # source already carries would defer the failure to put time, with a
        # message about a missing credential rather than a dropped session.
        if osw is not None:
            kwargs["osw"] = osw
        return super().from_other(other, **kwargs)

    def get(self) -> IO:
        self._init()
        file = self.osw.mw_site.images[self.title]
        # return file.download() # in-memory - limited by available RAM

        # use web api
        full_title = f"{self.namespace}:{self.title}"
        web_api_failed = False
        file_not_found = False
        response = None
        try:
            url = (
                f"{self.osw.mw_site.scheme}://"
                f"{self.osw.mw_site.host}"
                f"{self.osw.mw_site.path}"
                f"api.php?action=download&format=json&title={full_title}"
            )
            # print("Use web api: ", url)
            response = self.osw.mw_site.connection.get(url, stream=True)
            api_error = response.headers.get("Mediawiki-Api-Error")
            if api_error is not None:
                if api_error == "download-notfound":
                    # File does not exist
                    file_not_found = True
                elif api_error == "badvalue":
                    # Extension FileApi not installed on the server
                    web_api_failed = True
                elif api_error == "readapidenied":
                    # no read permissions on file
                    response.status_code = 403

        except Exception:
            web_api_failed = True
        if file_not_found:
            raise Exception("File does not exist: " + full_title)
        if web_api_failed:
            # fallback: use direct download
            url = file.imageinfo["url"]
            _logger.warning(
                f"Extension FileApi not installed on the server. Fallback: use "
                f"direct download from {url}"
            )
            response = self.osw.mw_site.connection.get(url, stream=True)

        if response.status_code != 200:
            raise Exception(
                "Download failed. Please note that bot or OAuth logins have in general "
                "no permission for direct downloads. Error: " + response.text
            )

        # for chunk in response.iter_content(1024):
        #    destination.write(chunk)
        # See https://stackoverflow.com/questions/16694907/
        #  download-large-file-in-python-with-requests
        response.raw.read = functools.partial(response.raw.read, decode_content=True)
        return response.raw

    def get_to(self, other: "FileController"):
        self._init()
        file = self.osw.mw_site.images[self.title]
        # return file.download() # in-memory - limited by available RAM

        with self.osw.mw_site.connection.get(
            file.imageinfo["url"], stream=True
        ) as response:
            # for chunk in response.iter_content(1024):
            #    destination.write(chunk)
            # See https://stackoverflow.com/questions/16694907/
            #  download-large-file-in-python-with-requests
            response.raw.read = functools.partial(
                response.raw.read, decode_content=True
            )
            other.put(response.raw)

    def put(self, file: IO, **kwargs: Dict[str, Any]):
        self._ensure_session()
        # extract file meta information
        if hasattr(file, "name") and file.name is not None:
            name = os.path.basename(file.name)
            suffix = ""
            if "." in name:
                suffix = "." + name.split(".")[-1]
            self._init(name, suffix)

        # file_page = self.osw._site.get_page(
        #   WtSite.GetPageParam(titles=[file_page_name])
        # ).pages[0]
        wf_params = {
            key: value
            for key, value in kwargs.items()
            if key in model.WikiFile.__fields__ and value is not None
        }
        se_params = {
            key: value
            for key, value in kwargs.items()
            if key in OSW.StoreEntityParam.__fields__ and value is not None
        }
        for key in ["entities", "namespace"]:
            se_params.pop(key, None)  # avoid duplicated kwargs
        # Upload before storing the entity: MediaWiki offers no transaction
        # across the two writes, so one of them can be left standing. A file
        # page without metadata is visibly incomplete, while metadata without a
        # file looks like a valid entity until someone tries to download it.
        page_existed = self.osw.mw_site.pages[f"{self.namespace}:{self.title}"].exists
        try:
            result = self.osw.mw_site.upload(
                file=file,
                filename=self.title,
                # comment="",
                # description="",
                ignore=True,
            )
        except mwclient.errors.APIError as e:
            reraise_upload_error(e, self.osw.site, self.title, self.suffix)
        assert_upload_success(result, self.title, self.osw.mw_site.host)
        self.osw.store_entity(
            OSW.StoreEntityParam(
                entities=[self.cast(model.WikiFile, **wf_params)],
                namespace=self.namespace,
                **store_params_for_upload(se_params, page_existed),
            )
        )

    def put_from(self, other: FileController, **kwargs: Dict[str, Any]):
        # if isinstance(file, LocalFileController) and self.suffix is None:
        #    lf = file.cast(LocalFileController)
        #    self.meta.wiki_page.title.removesuffix(lf.path.suffix)
        #    self.meta.wiki_page.title += lf.path.suffix
        # copy over metadata
        if self.label == [model.Label(text="Unnamed file")]:
            self.label = other.label
        super().put_from(other, **kwargs)

    def delete(self):
        self._ensure_session()
        file_page_name = f"{self.namespace}:{self.title}"
        file_page = self.osw.site.get_page(
            WtSite.GetPageParam(titles=[file_page_name])
        ).pages[0]
        if file_page.exists:
            file_page.delete()

    @property
    def url(self):
        self._ensure_session()
        return (
            f"{self.osw.mw_site.scheme}://{self.osw.mw_site.host}"
            f"/wiki/File:{self.title}"
        )

    def _ensure_session(self) -> OSW:
        """The session, connecting on first use when none was passed in.

        A file that is about to be uploaded has no URL yet - that is what the
        upload produces - so the URL is only one of the ways to find the wiki.
        Without one the registered credentials decide, and they are only
        unambiguous when there is exactly one.
        """
        if self.osw is None:
            self.osw = session_for(self._session_url())
        return self.osw

    def _session_url(self) -> str:
        """The wiki to connect to: the file's own URL, else the credential's."""
        try:
            return self._url()
        except ValueError:
            pass
        registered = _registered_credentials()
        if len(registered) == 1:
            return next(iter(registered))
        if not registered:
            raise ValueError(
                f"{type(self).__name__} has no download_url or access_url and "
                "no credential is registered. Pass osw= explicitly or register "
                "one with oold.backend.auth.set_credential."
            )
        raise ValueError(
            f"{type(self).__name__} has no download_url or access_url, and "
            f"credentials are registered for {', '.join(sorted(registered))}. "
            "Pass osw= explicitly to say which wiki this file belongs to."
        )

    def _init(self, name=None, suffix=None):
        self._ensure_session()
        # set the name attribute to the actual file name, e.g., "image.png"
        if self.name is None:
            self.name = name
        if suffix is None:
            title = get_title(self)
            if "." in title:
                suffix = "." + title.split(".")[-1]
            else:
                suffix = ""
        if self.suffix is None:
            self.suffix = suffix
        self.name = self.name.removesuffix(self.suffix)
        # Set the title from OSW-ID + suffix, e.g.,
        # "OSWeedfa07ad404421b8622e0099624d254.png"
        if self.title is None:
            self.title = get_title(self)
            self.title = self.title.removesuffix(self.suffix)
            self.title += self.suffix
        if self.namespace is None:
            self.namespace = get_namespace(self)
        # update meta information
        if not hasattr(self, "meta") or self.meta is None:
            self.meta = model.Meta()
        if not hasattr(self.meta, "wiki_page") or self.meta.wiki_page is None:
            self.meta.wiki_page = model.WikiPage()
        self.meta.wiki_page.title = self.title
        self.meta.wiki_page.namespace = self.namespace
