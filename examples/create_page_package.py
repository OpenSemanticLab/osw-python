import os

import osw.model.page_package as package
from osw.wtsite import WtSite

pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)

wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)

package_repo_org = "OpenSemanticWorld-Packages"
package_repo = "world.opensemantic.core"
package_id = "world.opensemantic.core"
package_name = "OSW Core"
package_subdir = "core"
package_branch = "main"

working_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "packages",
    package_repo,
)

bundle = package.PagePackageBundle(
    publisher="OpenSemanticWorld",
    author=["Simon Stier"],
    language="en",
    publisherURL=f"https://github.com/{package_repo_org}/{package_repo}",
    packages={
        f"{package_name}": package.PagePackage(
            globalID=f"{package_id}",
            label=package_name,
            version="0.2.1",
            description="Provides core functionalities of OpenSemanticWorld / OpenSemanticLab",
            baseURL=f"https://raw.githubusercontent.com/{package_repo_org}/{package_repo}/{package_branch}/{package_subdir}/",
        )
    },
)

wtsite.create_page_package(
    package.PagePackageConfig(
        name=package_name,
        config_path=os.path.join(working_dir, "packages.json"),
        content_path=os.path.join(working_dir, package_subdir),
        bundle=bundle,
        titles=[
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
)
