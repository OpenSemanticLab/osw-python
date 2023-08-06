from osw.auth import CredentialManager
from osw.controller.file.wiki import WikiFileController
from osw.core import OSW, model
from osw.wtsite import WtSite

# run with: tox -e test -- --wiki_domain domain --wiki_username user --wiki_password pass


def test_file_controller(wiki_domain, wiki_username, wiki_password):
    cm = CredentialManager()
    cm.add_credential(
        CredentialManager.UserPwdCredential(
            iri=wiki_domain, username=wiki_username, password=wiki_password
        )
    )
    wtsite = WtSite(WtSite.WtSiteConfig(iri=wiki_domain, cred_mngr=cm))
    # site = mwclient.Site(host=wiki_domain, scheme="http")
    # site.login(username=wiki_username, password=wiki_password)
    # wtsite = WtSite(WtSite.WtSiteLegacyConfig(site=site))
    osw = OSW(site=wtsite)

    list_of_categories = [
        "Category:OSW11a53cdfbdc24524bf8ac435cbf65d9d",  # WikiFile
        "Category:OSW3e3f5dd4f71842fbb8f270e511af8031",  # LocalFile
    ]
    for i, cat in enumerate(list_of_categories):
        mode = "append"
        if i == 0:
            mode = "replace"
        osw.fetch_schema(OSW.FetchSchemaParam(schema_title=cat, mode=mode))

    from osw.controller.file.local import LocalFileController

    lf = model.LocalFile(label=[model.Label(text="Test File")]).cast(
        LocalFileController
    )
    lf.path = "tests/integration/test.svg"

    # wf = WikiFileController.from_local(lf) # does not work due to missing attributes 'title' and 'osw'
    wf = WikiFileController(label=[model.Label(text="Test File")], osw=osw)
    wf.put_from(lf)
    # print(wf)

    title = wf.namespace + ":" + wf.title
    # title = "File:OSW1b3fea404fe344c78ffd2d7a46bb468e.svg"
    wf2 = osw.load_entity(title).cast(WikiFileController, osw=osw)
    lf2 = LocalFileController(
        label=[model.Label(text="Test File2")], path="tests/integration/test2.svg"
    )
    lf2.put_from(wf2)
    # wf2.get_to(lf2)

    lf2.delete()
    wf2.delete()
