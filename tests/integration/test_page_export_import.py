import uuid

from osw.auth import CredentialManager
from osw.core import OSW
from osw.wtsite import WtPage, WtSite

# run with: tox -e test -- --wiki_domain domain --wiki_username user --wiki_password pass


def _test_ontology_import(wiki_domain, wiki_username, wiki_password):
    """this test does not run with a bot account"""
    cm = CredentialManager()
    cm.add_credential(
        CredentialManager.UserPwdCredential(
            iri=wiki_domain, username=wiki_username, password=wiki_password
        )
    )
    wtsite = WtSite(WtSite.WtSiteConfig(iri=wiki_domain, cred_mngr=cm))

    osw = OSW(site=wtsite)

    p = osw.site.get_page(WtSite.GetPageParam(titles=["Main_Page"])).pages[0]
    res = p.export_xml()
    assert res.success is True

    p2 = osw.site.get_page(
        WtSite.GetPageParam(titles=["Item:" + OSW.get_osw_id(uuid.uuid4())])
    ).pages[0]
    res2 = p2.import_xml(
        WtPage.ImportConfig(
            xml=res.xml,
            summary="test import",
            source_domain="wiki-dev.open-semantic-lab.org",
        )
    )
    assert res2.success is True
    assert res2.imported_title == p2.title
    assert res2.imported_revisions > 0

    p2.delete()
