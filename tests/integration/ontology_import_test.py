import os

from osw.auth import CredentialManager
from osw.core import OSW, model
from osw.ontology import ImportConfig, OntologyImporter
from osw.wiki_tools import SearchParam
from osw.wtsite import WtSite

# run with: tox -e test -- --wiki_domain domain --wiki_username user --wiki_password pass


def test_ontology_import(wiki_domain, wiki_username, wiki_password):

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
        "Category:OSW725a3cf5458f4daea86615fcbd0029f8",  # OwlClass
        "Category:OSW6b9ef2784a934b8ab96523366e23e906",  # OwlIndividual
        "Category:Item",
        "Category:ObjectProperty",
        "Category:DataProperty",
        "Category:AnnotationProperty",
    ]
    for i, cat in enumerate(list_of_categories):
        mode = "append"
        if i == 0:
            mode = "replace"
        osw.fetch_schema(OSW.FetchSchemaParam(schema_title=cat, mode=mode))

    ontology_name = "example_ontology"

    ex = model.Ontology(
        name="Example",
        iri="http://example.com",
        prefix="http://example.com/",
        prefix_name="example",
        link="http://example.com",
    )

    import_config = ImportConfig(
        ontology_name=ontology_name,
        ontologies=[ex],
        file=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), f"{ontology_name}.ttl"
        ),
        base_class=model.OwlClass,
        base_class_title="Category:OSW725a3cf5458f4daea86615fcbd0029f8",  # OwlClass
        dump_files=True,
        dump_path=os.path.dirname(os.path.abspath(__file__)),
        dry_run=False,
    )

    # import ontologies
    importer = OntologyImporter(
        osw=osw,
    )
    importer.import_ontology(import_config)

    smw_import_page = wtsite.get_page(
        WtSite.GetPageParam(titles=["MediaWiki:Smw_import_example"])
    ).pages[0]

    expected = """http://example.com/|[http://example.com Example]
 R7k3ssL7gUxsfWuVsXWDXYF|Type:Text
 R9avr2pWFWEML712PSKDfcq|Type:Page
 REh2qNSARmKpPuwrJmr5Pu|Type:Page
 RqSw2tmyIfMbLNbk0NPkKa|Type:Text
 RBfJambxhZvFDQYeKK2zzeH|Category
 RDDfNZfAHDafrgYXW6rtT14|Category
 RDnVhTMcRkWFpWWnAprFlO0|Category
 RD2X6TQT0bKVpXehgObBb7O|Item"""

    actual = smw_import_page._content  # get_slot_content("main")
    assert actual == expected

    search_param = SearchParam(
        query="[[Example:ObjectPropertyA::Category:OSWb1e6910f1e3d567aaed30b83ac887708]]"
    )
    full_page_titles = osw.site.semantic_search(search_param)
    assert "Category:OSW51f195014de65ebe9f08994b21498cae" in full_page_titles

    osw.delete_entity(
        OSW.DeleteEntityParam(
            entities=importer._entities, comment="[bot] delete test data"
        )
    )
