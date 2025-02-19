import importlib
import os

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.core import OSW
from osw.wiki_tools import SearchParam
from osw.wtsite import WtSite

# Run with:
# tox -e test -- --wiki_domain domain --wiki_username user --wiki_password pass


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
    osw_obj = OSW(site=wtsite)

    list_of_categories = [
        "Category:OSW725a3cf5458f4daea86615fcbd0029f8",  # OwlClass
        "Category:OSW6b9ef2784a934b8ab96523366e23e906",  # OwlIndividual
        "Category:Item",
        "Category:ObjectProperty",
        "Category:DataProperty",
        "Category:AnnotationProperty",
        "Category:OSW662db0a2ad0946148422245f84e82f64",  # OwlOntology
    ]
    for i, cat in enumerate(list_of_categories):
        mode = "append"
        if i == 0:
            mode = "replace"
        osw_obj.fetch_schema(OSW.FetchSchemaParam(schema_title=cat, mode=mode))

    importlib.reload(model)
    from osw.ontology import ImportConfig, OntologyImporter

    ontology_name = "example_ontology"

    ex = model.OwlOntology(
        name="Example",
        label=[model.Label(text="Example Ontology", lang="en")],
        iri="http://example.com",
        prefix="http://example.com/",
        prefix_name="example",
        see_also=["http://example.com"],
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
    importer = OntologyImporter(osw=osw_obj)
    importer.import_ontology(import_config)

    smw_import_page = wtsite.get_page(
        WtSite.GetPageParam(titles=["MediaWiki:Smw_import_example"])
    ).pages[0]

    expected = """http://example.com/ | [http://example.com Example]
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

    property_name = None
    if import_config.property_naming_policy == "label":
        property_name = "objectPropertyA"
    elif import_config.property_naming_policy == "prefixed_label":
        property_name = (
            f"example{import_config.property_naming_prefix_delimiter}objectPropertyA"
        )
    search_param = SearchParam(
        query=f"[[{property_name}::Category:OSWb1e6910f1e3d567aaed30b83ac887708]]"
    )
    full_page_titles = osw_obj.site.semantic_search(search_param)
    print(full_page_titles)
    # Not reliable, because the SMW store is not updated immediately
    # assert "Category:OSW51f195014de65ebe9f08994b21498cae" in full_page_titles

    # Not reliable due to parallel test execution using the same osw instance and
    #  page ids
    # osw_obj.delete_entity(
    #     OSW.DeleteEntityParam(
    #         entities=importer._entities, comment="[bot] delete test data"
    #     )
    # )
