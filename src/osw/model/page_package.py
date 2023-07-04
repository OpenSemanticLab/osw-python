import os
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel


class PagePackagePageSlot(BaseModel):
    url: Optional[str]
    urlPath: Optional[str]


class PagePackagePage(BaseModel):
    """Dataclass for Page.
    Attributes are partly already defined in the specification of
    https://www.mediawiki.org/wiki/Extension:Page_Exchange"""

    name: str
    """The name (minus of the namespace) of a wiki page."""
    label: Optional[str]
    """The display label of the page."""
    namespace: Union[str, int]
    """The namespace code for the namespace of the wiki page, though stored as
    a string (like "NS_TEMPLATE"). The default is "NS_MAIN"."""
    url: Optional[str]
    """The URL at which the contents of the page can be found. This can be any URL, and
    does not have to be part of a wiki. If you are using a MediaWiki wiki page for the
    URL, make sure that the URL ends with "?action=raw" (or "&action=raw"), so that only
    the actual wikitext for the page is retrieved."""
    urlPath: Optional[str]
    """Similar to url, but gets appended to the baseURL value set for the package, if
    one was set."""
    # todo: include originURL or at PagePackage or Bundle level?
    fileURL: Optional[str]
    """ If this is a file/image page (i.e. with a "namespace" value of "NS_FILE"), this
    parameter holds the actual file, while the "url" parameter holds a URL containing
    the text contents of the wiki page."""
    fileURLPath: Optional[str]
    """Similar to fileURL, but gets appended to the baseURL value set for the package,
    if one was set."""
    slots: Dict[str, PagePackagePageSlot]
    """Slots used to store data, e.g., the main slot, storing the wiki text of the
    page. Other slots could be jsondata, jsonschema etc."""


class PagePackageNamespaceSettings(BaseModel):
    """The group of settings, per namespace, that together dictate the structure of the
    directory.
    Attributes are partly already defined in the specification of
    https://www.mediawiki.org/wiki/Extension:Page_Exchange"""

    namespace: str
    """The namespace code for this namespace, though stored as a string (like
    "NS_TEMPLATE")."""
    fileNamePrefix: Optional[str]
    """The prefix (potentially including slashes) for any file that corresponds to
    a page in this namespace."""
    fileNameSuffix: Optional[str]
    """The suffix (if any) for any file that corresponds to a page in this namespace."""
    actualFileNamePrefix: Optional[str]
    """ Used only for the "NS_FILE" namespace; specifies the prefix for the actual files
    (e.g., the images)."""
    actualFileNameSuffix: Optional[str]
    """Used only for the "NS_FILE" namespace; specifies the suffix for the actual
    files."""


class PagePackageDirectoryStructure(BaseModel):
    """For pages stored within a single repository (like GitHub), specifies the
    structure of that repository, instead of (or in addition to) any pages explicitly
    listed.
    Attributes are partly already defined in the specification of
    https://www.mediawiki.org/wiki/Extension:Page_Exchange"""

    service: Optional[str] = "GitHub"
    """The service being used to hold the data on individual pages. Currently only
    value is supported for this: "GitHub"."""
    accountName: str
    """The name of the account, i.e. the GitHub username of the repository."""
    repositoryName: str
    """The name of the specific repository."""
    namespaceSettings: PagePackageNamespaceSettings
    """The group of settings, per namespace, that together dictate the structure of the
    directory."""


class PagePackage(BaseModel):
    """A package of pages.
    Attributes are partly already defined in the specification of
    https://www.mediawiki.org/wiki/Extension:Page_Exchange"""

    globalID: str
    """(mandatory) A text identifier for this package, which is ideally globally
    unique. Ideally it uses reverse domain name notation. For example, for a package
    in the Spanish language for a CRM data structure, created by a company called
    Acme, whose internet domain is acme.com, the package identifier could be
    "com.acme.CRM.es". You can feel free to be creative within this system. For
    example, if you are publishing a package on your own and do not have your own
    internet domain, but you do have a username on mediawiki.org ("Joey User"),
    then you could give such a package the identifier
    "org.mediawiki.user.Joey_User.CRM.es". The important thing is uniqueness. It's
    also important, once people have started using a package, not to change its
    global ID - changing it would prevent people who have already downloaded the
    package from updating to more recent versions."""
    label: Optional[str]
    """The display label of the package."""
    description: str
    """A description of the page package."""
    publisher: Optional[str]
    """The default publisher."""
    publisherURL: Optional[str]
    """The default URL for the publisher."""
    author: Optional[List[str]]
    """The default author."""
    language: Optional[str]
    """The default language for all defined packages, using the (usually) two-letter
    IETF language tag for that language."""
    url: Optional[str]
    """A URL for a web page describing this entire package, if one exists."""
    version: str
    """A version number for the package, which can be updated so that users know if
    their local copy of the package is out of date."""
    licenseName: Optional[str]
    """The default license under which these packages are published."""
    requiredExtensions: Optional[List[str]]
    """An array of the names of any extensions required for this package to work. (In
    the future, this parameter may also allow defining specific versions that are
    required for specific extensions, but this is not currently possible.)"""
    requiredPackages: Optional[List[str]]
    """An array of the names of any additional packages required by this package."""
    baseURL: str
    """Holds a URL fragment (like 'https://example.com/packages/') that should be
    prepended to the urlPath or fileURLPath values set for any individual pages."""
    pages: Optional[List[PagePackagePage]]
    """The set of pages in this package."""
    directoryStructure: Optional[PagePackageDirectoryStructure]
    """For pages stored within a single repository (like GitHub), specifies the
    structure of that repository, instead of (or in addition to) any pages explicitly
    listed."""


class PagePackageBundle(BaseModel):
    """Bundle of page packages.
    Attributes are partly already defined in the specification of
    https://www.mediawiki.org/wiki/Extension:Page_Exchange"""

    publisher: Optional[str]
    """The default publisher."""
    publisherURL: Optional[str]
    """The default publisherURL."""
    author: Optional[List[str]]
    """The default author."""
    language: Optional[str] = "en"
    """The default language for all defined packages, using the
    (usually) two-letter IETF language tag for that language."""
    licenseName: Optional[str] = "CC BY-NC 4.0"
    """The default license under which these packages are published."""
    packages: Dict[str, PagePackage]
    """Holds the set of packages, with the package name as the key
    and the set of package parameters as the values."""


class PagePackageConfig(BaseModel):
    """A config for a page package"""

    name: str
    """The name (label) of the package."""
    config_path: Union[str, Path]
    """The path of the generated json file (package.json).
    Will be created automatically if not existing"""
    content_path: Optional[Union[str, Path]] = ""
    """The directory where the content (pages, files) is stored.
    Will be created automatically if not existing."""
    titles: List[str]
    """List of page titles."""
    # replace: Optional[bool] = False
    bundle: PagePackageBundle
    """Bund of pages."""
    skip_slot_suffix_for_main: Optional[bool] = False
    include_files: Optional[bool] = True

    def __init__(self, **data):
        """Originally, the dataclass.__post_init_() method was used here.
        Pydantic does not implement anything similar yet. According to
        https://github.com/pydantic/pydantic/issues/1729#issuecomment-1300576214
        no __post_init__ method will be available until Pydantic v2. Then an
        analogous function will be implemented and any in a BaseModel class defined
        method named 'model_post_init(self, **kwargs)' will be called after
        init."""
        super().__init__(**data)
        if self.content_path == "":
            self.content_path = os.path.dirname(self.config_path)


class PagePackageMetaData(BaseModel):
    """Metadata for a page package. This data needed to create a page package and
    included in the page package."""

    name: str
    """The name (label) of the page package."""
    repo: str
    """Page package repository name - usually the GitHub repository name"""
    id: str
    """Page package ID - usually the same as package_repo"""
    subdir: str
    """Page package subdirectory - usually resembling parts of the package name"""
    branch: str
    """Page package branch - usually 'main'."""
    repo_org: str
    """(GitHub) Organization hosting the package repository"""
    description: str
    """Page package description"""
    language: str = "en"
    """Page package language - usually the two-letter IETF language tag for that
    language"""
    version = "0.2.1"
    """Page package version - use semantic versioning"""
    author: List[str]
    """Author(s) of the page package"""
    publisher: str
    """Publisher of the page package."""
    page_titles: List[str]
    """List of the page titles (full page titles with namespace, e.g. 'Category:Entity')
     to be packaged."""

    requiredExtensions: Optional[List[str]]
    """The default value for PagePackage.requiredExtensions.
    An array of the names of any extensions required for this package to work. (In
    the future, this parameter may also allow defining specific versions that are
    required for specific extensions, but this is not currently possible.)"""
    requiredPackages: Optional[List[str]]
    """The default value for PagePackage.requiredPackages.
    An array of the names of any additional packages required by this package."""


# Special namespace mappings (default is namespace_const = "NS_" + namespace.upper())
NAMESPACE_CONST_TO_NAMESPACE_MAPPING = {
    # SMW: https://github.com/SemanticMediaWiki/SemanticMediaWiki/blob/ebb03c1537810f4ee8c1a25198b8d2e243cc38a1/src/NamespaceManager.php#L119
    "SMW_NS_PROPERTY": "Property",
    "SMW_NS_PROPERTY_TALK": "Property_talk",
    "SMW_NS_CONCEPT": "Concept",
    "SMW_NS_CONCEPT_TALK": "Concept_talk",
    "SMW_NS_SCHEMA": "smw/schema",
    "SMW_NS_SCHEMA_TALK": "smw/schema_talk",
    "SMW_NS_RULE": "Rule",
    "SMW_NS_RULE_TALK": "Rule_talk",
}
# inverse
NAMESPACE_TO_NAMESPACE_CONST_MAPPING = {
    v: k for k, v in NAMESPACE_CONST_TO_NAMESPACE_MAPPING.items()
}
