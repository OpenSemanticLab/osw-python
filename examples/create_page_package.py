from pathlib import Path

import osw.model.page_package as package
from osw.wiki_tools import create_page_package

# Provide information on the page package to be created
package_meta_data = package.PagePackageMetaData(
    # Package name
    name="OSW Core",
    # Package repository name - usually the GitHub repository name
    repo="world.opensemantic.core",
    # Package ID - usually the same as repo
    id="world.opensemantic.core",
    # Package subdirectory - usually resembling parts of the package name
    subdir="core",
    # Package branch - usually "main"
    branch="main",
    # (GitHub) Organization hosting the package repository
    repo_org="OpenSemanticWorld-Packages",
    # Provide a package description
    description=(
        "Provides core functionalities of OpenSemanticWorld / OpenSemanticLab"
    ),
    # Specify the package version - use semantic versioning
    version="0.2.1",
    # Authors
    authors=["Simon Stier", "Lukas Gold"],
    # Publisher
    publisher="OpenSemanticWorld",
    # List the full page titles of the pages to be included in the package
    # You can include a comment in the same line, stating the page label
    page_titles=[
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
    ],
)
# Provide the information needed (only) to create the page package
package_creation_config = package.PagePackageCreationConfig(
    # Specify the path to the credentials file
    pwd_file_path=Path(__file__).parent / "accounts.pwd.yaml",
    # Specify the domain of the OSW/OSL instance to load pages from
    domain="wiki-dev.open-semantic-lab.org",
    # Specify the path to the working directory - where the package is stored on disk
    working_dir=Path(__file__).parents[2] / "packages" / package_meta_data.repo,
)
# Create the page package
create_page_package(
    meta_data=package_meta_data,
    creation_config=package_creation_config,
)
