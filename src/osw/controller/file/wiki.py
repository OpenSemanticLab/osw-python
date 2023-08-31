import functools
import os
from typing import IO, Optional

from osw.controller.file.base import FileController
from osw.controller.file.remote import RemoteFileController
from osw.core import OSW, model
from osw.utils.wiki import get_namespace, get_title
from osw.wtsite import WtSite


class WikiFileController(model.WikiFile, RemoteFileController):
    osw: OSW
    namespace: Optional[str] = "File"
    title: Optional[str] = None
    suffix: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def get(self) -> IO:
        self._init()
        file = self.osw.site._site.images[self.title]
        # return file.download() # in-memory - limited by available RAM

        response = self.osw.site._site.connection.get(
            file.imageinfo["url"], stream=True
        )
        # for chunk in response.iter_content(1024):
        #    destination.write(chunk)
        # see https://stackoverflow.com/questions/16694907/download-large-file-in-python-with-requests
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
            # see https://stackoverflow.com/questions/16694907/download-large-file-in-python-with-requests
            response.raw.read = functools.partial(
                response.raw.read, decode_content=True
            )
            other.put(response.raw)

    def put(self, file: IO):
        # extract file meta information
        if hasattr(file, "name") and file.name is not None:
            name = os.path.basename(file.name)
            suffix = ""
            if "." in name:
                suffix = "." + name.split(".")[-1]
            self._init(name, suffix)

        # file_page = self.osw._site.get_page(WtSite.GetPageParam(titles=[file_page_name])).pages[0]
        self.osw.store_entity(
            OSW.StoreEntityParam(
                entities=[self.cast(model.WikiFile)], namespace=self.namespace
            )
        )
        self.osw.site._site.upload(
            file=file,
            filename=self.title,
            # comment="",
            # description="",
            ignore=True,
        )

    def put_from(self, other: FileController):
        # if isinstance(file, LocalFileController) and self.suffix is None:
        #    lf = file.cast(LocalFileController)
        #    self.meta.wiki_page.title.removesuffix(lf.path.suffix)
        #    self.meta.wiki_page.title += lf.path.suffix
        return super().put_from(other)

    def delete(self):
        file_page_name = f"{self.namespace}:{self.title}"
        file_page = self.osw.site.get_page(
            WtSite.GetPageParam(titles=[file_page_name])
        ).pages[0]
        if file_page.exists:
            file_page.delete()

    def _init(self, name=None, suffix=None):
        # set the name attribute to the actual file name, e. g. "image.png"
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
        # set the title from OSW-ID + suffix, e. g. "OSWeedfa07ad404421b8622e0099624d254.png"
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
