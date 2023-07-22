from importlib import reload
from pathlib import Path

import mwclient

import osw.model.entity as model
from osw.core import OSW
from osw.wtsite import WtSite

DEPENDENCIES = {
    "Entity": "Category:Entity",
    "Item": "Category:Item",
    "WikiFile": "Category:OSW11a53cdfbdc24524bf8ac435cbf65d9d",
}


def fetch_dependencies(wtsite_obj: WtSite):
    osw = OSW(site=wtsite_obj)
    categories_fpt = DEPENDENCIES.values()
    for i, cat in enumerate(categories_fpt):
        mode = "append"
        # if i == 0:
        #     mode = "replace"
        osw.fetch_schema(OSW.FetchSchemaParam(schema_title=cat, mode=mode))


def check_dependencies():
    dependencies_met = True
    for key in DEPENDENCIES.keys():
        if not hasattr(model, key):
            dependencies_met = False
            break
    return dependencies_met


def main(wiki_domain: str, wiki_username: str, wiki_password: str):
    dependencies_met = check_dependencies()
    if not dependencies_met:
        # For local testing without tox
        if wiki_domain is None or wiki_domain == "None":
            # Make sure that the password file is available
            cwd = Path(__file__).parent.absolute()
            pw_fp = cwd.parents[1] / "examples" / "accounts.pwd.yaml"
            wtsite = WtSite.from_domain(
                domain="wiki-dev.open-semantic-lab.org",
                password_file=str(pw_fp),
            )
        # For testing with tox
        else:
            site = mwclient.Site(host=wiki_domain)
            site.login(username=wiki_username, password=wiki_password)
            wtsite = WtSite(WtSite.WtSiteLegacyConfig(site=site))

        fetch_dependencies(wtsite_obj=wtsite)


if __name__ == "__main__":
    main()
    reload(model)
