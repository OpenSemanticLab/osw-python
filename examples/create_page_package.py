from pathlib import Path

import osw.model.page_package as package
from osw.wtsite import WtSite

# Specify the path to the credentials file
pwd_file_path = Path(__file__).parent / "accounts.pwd.yaml"

# Specify the domain of the OSW/OSL instance to load pages from
domain = "wiki-dev.open-semantic-lab.org"


# Provide information on the package to be created
# Package name
package_name = "OSW Core"
# Package repository name - usually the GitHub repository name
package_repo = "world.opensemantic.core"
# Package ID - usually the same as package_repo
package_id = "world.opensemantic.core"
# Package subdirectory - usually resembling parts of the package name
package_subdir = "core"
# Package branch - usually "main"
package_branch = "main"
# (GitHub) Organization hosting the package repository
package_repo_org = "OpenSemanticWorld-Packages"
# Provide a description
package_description = (
    "Provides core functionalities of OpenSemanticWorld / OpenSemanticLab"
)
# Specify version
package_version = "0.2.1"
# Authors
authors = ["Simon Stier", "Lukas Gold"]
# Publisher
publisher = "OpenSemanticWorld"
# List the full page titles of the pages to be included in the package
# You can include a comment in the same line, stating the page label
page_titles = [
    "Module:Lustache",
    "Module:Lustache/Context",
    "Module:Lustache/Renderer",
    "Module:Lustache/Scanner",
    "Module:Entity",
    "Module:MwJson",
    "JsonSchema:Label",
    "JsonSchema:Description",
    "Category:Category",
    "Category:Entity",
    "Category:Item",
    "Template:Helper/UI/Tiles/Grid",
    "Template:Helper/UI/Tiles/Tile",
]


# Specify the path to the working directory - where the package is stored on disk
working_dir = Path(__file__).parents[2] / "packages" / package_repo


# Usually, you won't need to change anything below this line
# ----------------------------------------------------------------------
# Create a WtSite instance to load pages from the specified domain
wtsite = WtSite.from_domain(domain, pwd_file_path)
# Create a PagePackageBundle instance
bundle = package.PagePackageBundle(
    publisher=publisher,
    author=authors,
    language="en",
    publisherURL=f"https://github.com/{package_repo_org}/{package_repo}",
    packages={
        f"{package_name}": package.PagePackage(
            globalID=f"{package_id}",
            label=package_name,
            version=package_version,
            description=package_description,
            baseURL=f"https://raw.githubusercontent.com/{package_repo_org}/"
            f"{package_repo}/{package_branch}/{package_subdir}/",
        )
    },
)
# Create a PagePackageConfig instance
config = package.PagePackageConfig(
    name=package_name,
    config_path=working_dir / "packages.json",
    content_path=working_dir / package_subdir,
    bundle=bundle,
    titles=page_titles,
)
# Create the page package in the working directory
wtsite.create_page_package(config=config)
