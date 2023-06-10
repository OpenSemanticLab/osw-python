import mwclient

# from osw.core import OSW
# from osw.wtsite import WtSite

# run with: tox -e test -- --wiki_domain domain --wiki_username user --wiki_password pass


def test_login(wiki_domain, wiki_username, wiki_password):
    site = mwclient.Site(host=wiki_domain)
    site.login(username=wiki_username, password=wiki_password)
    # wtsite = WtSite(WtSite.WtSiteLegacyConfig(site=site))
    # osw = OSW(site=wtsite)
