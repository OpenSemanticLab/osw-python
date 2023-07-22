import mwclient

import osw.model.entity as model
from osw.core import OSW
from osw.wiki_tools import SearchParam
from osw.wtsite import WtSite

# run with: tox -e test -- --wiki_domain domain --wiki_username user --wiki_password pass


def test_store_and_load(wiki_domain, wiki_username, wiki_password):
    site = mwclient.Site(host=wiki_domain)
    site.login(username=wiki_username, password=wiki_password)
    wtsite = WtSite(WtSite.WtSiteLegacyConfig(site=site))
    osw = OSW(site=wtsite)

    my_entity = model.Item(label=[model.Label(text="MyItem")])

    osw.store_entity(my_entity)

    my_entity2 = osw.load_entity("Item:" + OSW.get_osw_id(my_entity.uuid))

    assert my_entity.label[0].text == my_entity2.label[0].text

    osw.delete_entity(my_entity)


def test_statement_creation(wiki_domain, wiki_username, wiki_password):
    site = mwclient.Site(host=wiki_domain)
    site.login(username=wiki_username, password=wiki_password)
    wtsite = WtSite(WtSite.WtSiteLegacyConfig(site=site))
    osw = OSW(site=wtsite)

    my_entity = model.Item(
        label=[model.Label(text="MyItem")],
        statements=[
            model.DataStatement(property="Property:TestProperty", value="TestValue")
        ],
    )

    osw.store_entity(my_entity)

    search_param = SearchParam(query="[[TestProperty::TestValue]]")
    full_page_titles = osw.site.semantic_search(search_param)
    assert f"Item:{OSW.get_osw_id(my_entity.uuid)}" in full_page_titles

    search_param = SearchParam(
        query="[[HasStatement.HasProperty::Property:TestProperty]]"
    )
    full_page_titles = osw.site.semantic_search(search_param)
    assert f"Item:{OSW.get_osw_id(my_entity.uuid)}" in full_page_titles

    osw.delete_entity(my_entity)
