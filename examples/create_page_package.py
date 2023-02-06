import os

import osw.model.page_package as package
from osw.wtsite import WtSite

pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)

wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)

package_name = "core"
working_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "PagePackages",
    package_name,
)

bundle = package.PagePackageBundle(
    publisher="OpenSemanticLab",
    author=["Simon Stier"],
    language="en",
    publisherURL="https://github.com/OpenSemanticLab/PagePackages",
    packages={
        "core": package.PagePackage(
            globalID=f"org.open-semantic-lab.{package_name}",
            version="0.1.2",
            description="Provides core functionalities of OpenSemanticLab",
            baseURL=f"https://raw.githubusercontent.com/OpenSemanticLab/PagePackages/main/{package_name}/",
        )
    },
)

wtsite.create_page_package(
    WtSite.PagePackageConfig(
        name=package_name,
        target_path=os.path.join(working_dir, f"{package_name}_packages.json"),
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
        ],
    )
)
