import os
import tempfile
import urllib.request
import zipfile

from osw.auth import CredentialManager
from osw.core import OSW
from osw.wtsite import WtSite


def test_offline_package_from_git(wiki_domain, wiki_username, wiki_password):
    cm = CredentialManager()
    cm.add_credential(
        CredentialManager.UserPwdCredential(
            iri=wiki_domain, username=wiki_username, password=wiki_password
        )
    )
    wtsite = WtSite(WtSite.WtSiteConfig(iri=wiki_domain, cred_mngr=cm))
    # create OSW instance which auto-registers as a oold backend
    osw_obj = OSW(site=wtsite)  # noqa: F841
    package = "world.opensemantic.core@v0.53.1"

    package_name, package_version = package.split("@")
    # define repo url,
    # e.g. https://github.com/OpenSemanticWorld-Packages/world.opensemantic.core
    git_url = "https://github.com/OpenSemanticWorld-Packages/" + package_name
    git_zip_url = git_url + "/archive/refs/tags/" + package_version + ".zip"

    # download package as zip
    # using a temp dir
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, "downloaded.zip")

        # Download the ZIP file
        urllib.request.urlretrieve(git_zip_url, zip_path)

        # Extract the ZIP file
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        result = osw_obj.site.read_page_package(
            WtSite.ReadPagePackageParam(
                storage_path=os.path.join(
                    temp_dir,
                    (
                        package_name + "-" + package_version[1:]
                        if package_version.startswith("v")
                        else package_version
                    ),
                )
            )
        )
        offline_pages = {page.title: page for page in result.pages}
        # print(f"Offline pages: {list(offline_pages.keys())}")

        assert (
            offline_pages["Category:Item"].get_slot_content("jsonschema")["title"]
            == "Item"
        )
