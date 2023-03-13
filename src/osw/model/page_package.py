from typing import List, Optional, Union
import os
from pydantic import BaseModel, Field


class PagePackagePageSlot(BaseModel):
    url: Optional[str]
    urlPath: Optional[str]


class PagePackagePage(BaseModel):
    name: str
    """The name (minus of the namespace) of a wiki page
    """
    label: Optional[str]
    """The display label of the page
    """
    namespace: Union[str, int]
    url: Optional[str]
    urlPath: Optional[str]
    fileURL: Optional[str]
    fileURLPath: Optional[str]
    slots: dict[str, PagePackagePageSlot]


class PagePackageNamespaceSettings(BaseModel):
    namespace: str
    fileNamePrefix: Optional[str]
    fileNameSuffix: Optional[str]
    actualFileNamePrefix: Optional[str]
    actualFileNameSuffix: Optional[str]


class PagePackageDirectoryStructure(BaseModel):
    service: Optional[str] = "GitHub"
    accountName: str
    repositoryName: str
    namespaceSettings: PagePackageNamespaceSettings


class PagePackage(BaseModel):
    globalID: str
    label: Optional[str]
    """The display label of the package
    """
    description: str
    publisher: Optional[str]
    publisherURL: Optional[str]
    author: Optional[List[str]]
    language: Optional[str]
    url: Optional[str]
    version: str
    licenseName: Optional[str]
    requiredExtensions: Optional[List[str]]
    requiredPackages: Optional[List[str]]
    baseURL: str  # todo: comment
    """
    """
    pages: Optional[List[PagePackagePage]]
    directoryStructure: Optional[PagePackageDirectoryStructure]


class PagePackageBundle(BaseModel):
    publisher: Optional[str]
    """The default publisher
    """
    publisherURL: Optional[str]
    """The default publisherURL
    """
    author: Optional[List[str]]
    """The default author
    """
    language: Optional[str] = "en"
    """The default language for all defined packages,
    using the (usually) two-letter IETF language tag for that language.
    """
    licenseName: Optional[str] = "CC BY-NC 4.0"
    """The default license under which these packages are published.
    """
    packages: dict[str, PagePackage]
    """Holds the set of packages, with the package name as the key
    and the set of package parameters as the values.
    """


class PagePackageConfig(BaseModel):
    name: str
    """The name (label) of the package
    """
    config_path: str
    """The path of the generated json file
    """
    # todo: which json file?
    content_path: Optional[str] = ""
    """
    The directory where the content (pages, files) is stored
    """
    titles: List[str]
    # replace: Optional[bool] = False
    bundle: PagePackageBundle
    skip_slot_suffix_for_main: Optional[bool] = False
    include_files: Optional[bool] = True

    def __post_init__(self):
        """Will be executed after the object is initialized, but before validation.
        """
        if self.content_path == "":
            self.content_path = os.path.dirname(self.config_path)


