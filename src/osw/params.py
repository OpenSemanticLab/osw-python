from osw.auth import CredentialManager  # noqa: F401
from osw.core import (  # noqa: F401
    OSW,
    OVERWRITE_CLASS_OPTIONS,
    AddOverwriteClassOptions,
    OverwriteOptions,
)
from osw.express import DataModel, OswExpress  # noqa: F401
from osw.wiki_tools import SearchParam  # noqa: F401
from osw.wtsite import WtPage, WtSite  # noqa: F401


# From osw.auth.CredentialManager:
class UserPwdCredential(CredentialManager.UserPwdCredential):
    pass


# Enum
# class CredentialFallback(CredentialManager.CredentialFallback):
#     pass


class CredentialConfig(CredentialManager.CredentialConfig):
    pass


# From osw.core.OSW:
class SchemaUnregistration(OSW.SchemaUnregistration):
    pass


class SchemaRegistration(OSW.SchemaRegistration):
    pass


# Enum
# class FetchSchemaMode(OSW.FetchSchemaMode):
#     pass


class FetchSchemaParam(OSW.FetchSchemaParam):
    pass


class LoadEntityParam(OSW.LoadEntityParam):
    pass


class OverwriteClassParam(OSW.OverwriteClassParam):
    pass


class StoreEntityParam(OSW.StoreEntityParam):
    pass


class DeleteEntityParam(OSW.DeleteEntityParam):
    pass


class QueryInstancesParam(OSW.QueryInstancesParam):
    pass


# From osw.wtsite.WtSite:
class WtSiteConfig(WtSite.WtSiteConfig):
    pass


class GetPageParam(WtSite.GetPageParam):
    pass


class ModifySearchResultsParam(WtSite.ModifySearchResultsParam):
    pass


class UploadPageParam(WtSite.UploadPageParam):
    pass


class CopyPagesParam(WtSite.CopyPagesParam):
    pass


class CreatePagePackageParam(WtSite.CreatePagePackageParam):
    pass


class ReadPagePackageParam(WtSite.ReadPagePackageParam):
    pass


class UploadPagePackageParam(WtSite.UploadPagePackageParam):
    pass


class DeletePageParam(WtSite.DeletePageParam):
    pass


# From osw.wtsite.WtPage:
class CopyPageConfig(WtPage.CopyPageConfig):
    pass


class PageDumpConfig(WtPage.PageDumpConfig):
    pass


class ExportConfig(WtPage.ExportConfig):
    pass


class ImportConfig(WtPage.ImportConfig):
    pass
