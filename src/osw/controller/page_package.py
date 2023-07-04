from pathlib import Path
from typing import Union

from pydantic import FilePath

import osw.model.page_package as model
from osw.auth import CredentialManager
from osw.model import page_package as package
from osw.model.static import OswBaseModel
from osw.wtsite import WtSite


class PagePackageController(model.PagePackageMetaData):
    """Adds controller logic to a package definitions to create / update it"""

    class CreationConfig(OswBaseModel):
        """Configuration for creating a page package. This is the data needed to create
        a page package but is not included in the page package."""

        domain: str
        """A string formatted as domain"""
        credentials_file_path: Union[str, FilePath]
        """Path to a existing credentials yaml files"""
        working_dir: Union[str, Path]
        """Working directory. Will be created automatically if not existing."""
        skip_slot_suffix_for_main: bool = False

    def create(
        self,
        creation_config: CreationConfig,
    ):
        """creates or updates the package

        Parameters
        ----------
        creation_config
            see PagePackageController.CreationConfig
        """
        # Create a WtSite instance to load pages from the specified domain
        wtsite = WtSite(
            WtSite.WtSiteConfig(
                iri=creation_config.domain,
                cred_mngr=CredentialManager(
                    cred_filepath=creation_config.credentials_file_path
                ),
            )
        )
        # Create a PagePackageBundle instance
        bundle = package.PagePackageBundle(
            publisher=self.publisher,
            author=self.author,
            language=self.language,
            publisherURL=f"https://github.com/{self.repo_org}/{self.repo}",
            packages={
                f"{self.name}": package.PagePackage(
                    globalID=f"{self.id}",
                    label=self.name,
                    version=self.version,
                    requiredExtensions=self.requiredExtensions,
                    requiredPackages=self.requiredPackages,
                    description=self.description,
                    baseURL=f"https://raw.githubusercontent.com/"
                    f"{self.repo_org}/"
                    f"{self.repo}/"
                    f"{self.branch}/"
                    f"{self.subdir}/",
                )
            },
        )
        # Create a PagePackageConfig instance
        config = package.PagePackageConfig(
            name=self.name,
            config_path=Path(creation_config.working_dir) / "packages.json",
            content_path=Path(creation_config.working_dir) / self.subdir,
            bundle=bundle,
            titles=self.page_titles,
            skip_slot_suffix_for_main=creation_config.skip_slot_suffix_for_main,
        )
        # Create the page package in the working directory
        wtsite.create_page_package(WtSite.CreatePagePackageParam(config=config))
