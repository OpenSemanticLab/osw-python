from typing import List, Optional, Union

from pydantic import BaseModel


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
    baseURL: str
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
