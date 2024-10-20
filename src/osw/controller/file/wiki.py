import functools
import os
from typing import IO, Any, Dict, List, Optional

from osw.controller.file.base import FileController
from osw.controller.file.remote import RemoteFileController
from osw.core import OSW, model
from osw.utils.wiki import get_namespace, get_title
from osw.wtsite import WtSite


class WikiFileController(model.WikiFile, RemoteFileController):
    """File controller for wiki files"""

    label: Optional[List[model.Label]] = [model.Label(text="Unnamed file")]
    """the label of the file, defaults to 'Unnamed file'"""
    osw: OSW
    """the OSW instance to connect with"""
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
        cls, other: FileController, osw: OSW, **kwargs: Dict[str, Any]
    ) -> "WikiFileController":
        return super().from_other(other, osw=osw, **kwargs)

    def get(self) -> IO:
        self._init()
        file = self.osw.site._site.images[self.title]
        # return file.download() # in-memory - limited by available RAM

        # use web api
        full_title = f"{self.namespace}:{self.title}"
        web_api_failed = False
        response = None
        try:
            url = (
                f"{self.osw.site._site.scheme}://"
                f"{self.osw.site._site.host}"
                f"{self.osw.site._site.path}"
                f"api.php?action=download&format=json&title={full_title}"
            )
            # print("Use web api: ", url)
            response = self.osw.site._site.connection.get(url, stream=True)
            api_error = response.headers.get("Mediawiki-Api-Error")
            if api_error is not None:
                if api_error == "download-notfound":
                    # File does not exist
                    raise Exception("File does not exist: " + full_title)
                elif api_error == "badvalue":
                    # Extension FileApi not installed on the server
                    web_api_failed = True
                elif api_error == "readapidenied":
                    # no read permissions on file
                    response.status_code = 403

        except Exception:
            web_api_failed = True
        if web_api_failed:
            # fallback: use direct download
            url = file.imageinfo["url"]
            print(
                "Extension FileApi not installed on the server. Fallback: use direct "
                "download from ",
                url,
            )
            response = self.osw.site._site.connection.get(url, stream=True)

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
        file = self.osw.site._site.images[self.title]
        # return file.download() # in-memory - limited by available RAM

        with self.osw.site._site.connection.get(
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
            if key in se_params:
                del se_params[key]  # avoid duplicated kwargs
        self.osw.store_entity(
            OSW.StoreEntityParam(
                entities=[self.cast(model.WikiFile, **wf_params)],
                namespace=self.namespace,
                **se_params,
            )
        )
        self.osw.site._site.upload(
            file=file,
            filename=self.title,
            # comment="",
            # description="",
            ignore=True,
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
        file_page_name = f"{self.namespace}:{self.title}"
        file_page = self.osw.site.get_page(
            WtSite.GetPageParam(titles=[file_page_name])
        ).pages[0]
        if file_page.exists:
            file_page.delete()

    @property
    def url(self):
        return (
            f"{self.osw.site._site.scheme}://{self.osw.site._site.host}"
            f"/wiki/File:{self.title}"
        )

    def _init(self, name=None, suffix=None):
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
        if not hasattr(self, "meta"):
            self.meta = model.Meta()
        elif self.meta is None:
            self.meta = model.Meta()
        if not hasattr(self.meta, "wiki_page") or self.meta.wiki_page is None:
            self.meta.wiki_page = model.WikiPage()
        self.meta.wiki_page.title = self.title
        self.meta.wiki_page.namespace = self.namespace
