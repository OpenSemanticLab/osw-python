from pathlib import Path

from pydantic import BaseModel
from typing_extensions import Optional, Union

import osw.model.entity as entity_model
from osw.auth import CredentialManager
from osw.core import OSW
from osw.model.static import OswBaseModel
from osw.wtsite import WtSite

# Definition of constants
# You will have to create your own credentials file following the provided
#  example_accounts.pwd.yaml file. The accounts.pwd.yaml file is listed in the
#  .gitignore and should never be committed to the repository.
CREDENTIALS_FILE_PATH_DEFAULT = Path(__file__).parents[1] / "accounts.pwd.yaml"
DEPENDENCIES = {
    "Entity": "Category:Entity",
    "Item": "Category:Item",
    "WikiFile": "Category:OSW11a53cdfbdc24524bf8ac435cbf65d9d",
    "LocalFile": "Category:OSW3e3f5dd4f71842fbb8f270e511af8031",
    "User": "Category:OSWd9aa0bca9b0040d8af6f5c091bf9eec7",
    "Group": "Category:OSWb8b6278763d54b0784eea9d3b3d183a4",
    "Location": "Category:OSW3d238d05316e45a4ac95a11d7b24e36b",
    "Site": "Category:OSW473d7a1ed48544d1be83b258b5810948",
    "Building": "Category:OSW4bcd4a99a73f482ea40ac4210dfab836",
    "BuildingFunction": "Category:OSW07a0faef5be94b788514a2dd5dca20bf",
    "Floor": "Category:OSW6c4212f1a39342be963d2b9efd19c5c2",
    "Room": "Category:OSWc5ed0ed1e33c4b31887c67af25a610c1",
    "RoomUsage": "Category:OSWac9f0e49d8024804bd7d77058322a3fe",
    "AreaUsageType": "Category:OSWae92be81cdb34d22844d4791ef790d93",
    "OrganizationalUnit": "Category:OSW3cb8cef2225e403092f098f99bc4c472",
    "Organization": "Category:OSW1969007d5acf40539642877659a02c23",
    "Association": "Category:OSWd9521d3054814dd29c2bcdbd9185d1f0",
    "Corporation": "Category:OSW5f4a3751d23e482d80fb0b72dcd6bc31",
    "Foundation": "Category:OSWd7085ef89b0e4a69ac4f2d28bda2d2c0",
    "University": "Category:OSW11ee14fb9f774b4b89bdb9bb89aac14d",
    "OrganizationalSubUnit": "Category:OSWfe3e842b804445c7bb0dd8ee61da2d70",
    "Department": "Category:OSW94aa074255374580b70337340c5ccc1b",
    "Faculty": "Category:OSWa01126bc9e9048988cb0f49e359015bc",
    "Institute": "Category:OSW5427361692374c8eaa6bd3733b92d343",
    "Person": "Category:OSW44deaa5b806d41a2a88594f562b110e9",
    "PersonRole": "Category:OSW5efde23b1d8c4e1c864ef039cb0616ed",
    "Project": "Category:OSWb2d7e6a2eff94c82b7f1f2699d5b0ee3",
    "ResearchOrganization": "Category:OSW789dcd084860478dbc60361a2da7c823",
    "GovernmentOrganization": "Category:OSW41ff0ef9d7cf4134bccf5bbbf1976f73",
}


# Definition of classes
class OswInstance(OswBaseModel):
    domain: str
    cred_fp: Union[str, Path]
    credentials_manager: Optional[CredentialManager]
    osw: Optional[OSW]
    wtsite: Optional[WtSite]

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        domain: str,
        cred_fp: Union[str, Path] = Path(CREDENTIALS_FILE_PATH_DEFAULT),
    ):
        super().__init__(**{"domain": domain, "cred_fp": cred_fp})
        self.credentials_manager = CredentialManager(cred_filepath=cred_fp)
        self.osw = OSW(
            site=WtSite(
                WtSite.WtSiteConfig(iri=domain, cred_mngr=self.credentials_manager)
            )
        )
        self.wtsite = self.osw.site

    def fetch_dependencies(
        self, unmet_dependencies: list = None, fetch_all: bool = False
    ):
        if unmet_dependencies is not None and not fetch_all:
            categories_fpt = [
                val for (key, val) in DEPENDENCIES.items() if key in unmet_dependencies
            ]
        else:
            categories_fpt = list(DEPENDENCIES.values())
        for i, cat in enumerate(categories_fpt):
            mode = "append"
            # if i == 0:
            #     mode = "replace"
            self.osw.fetch_schema(OSW.FetchSchemaParam(schema_title=cat, mode=mode))

    class CheckedDependencies(BaseModel):
        dependencies_met: bool
        unmet_dependencies: list

    @staticmethod
    def check_dependencies(dependencies: dict = None):
        if dependencies is None:
            dependencies = DEPENDENCIES
        dependencies_met = True
        unmet_dependencies = list()
        for key in dependencies.keys():
            if not hasattr(entity_model, key):
                dependencies_met = False
                unmet_dependencies.append(key)
        return OswInstance.CheckedDependencies(
            **{
                "dependencies_met": dependencies_met,
                "unmet_dependencies": unmet_dependencies,
            }
        )

    def ensure_dependencies(
        self,
        dependencies: dict = None,
        refetch_dependencies: bool = False,
    ):
        if dependencies is None:
            dependencies = DEPENDENCIES
        ret_val = self.check_dependencies(dependencies)
        dependencies_met = ret_val.dependencies_met
        unmet = ret_val.unmet_dependencies
        if not dependencies_met:
            self.fetch_dependencies(
                unmet_dependencies=unmet, fetch_all=refetch_dependencies
            )


if __name__ == "__main__":
    osw_instance = OswInstance(domain="wiki-dev.open-semantic-lab.org")
    osw_instance.ensure_dependencies()
    print("Dependencies ensured.")
