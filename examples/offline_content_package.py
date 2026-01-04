import os
from pathlib import Path

from osw import wiki_tools
from osw.auth import CredentialManager
from osw.core import OSW
from osw.model.page_package import PagePackage, PagePackageBundle, PagePackageConfig
from osw.params import CreatePagePackageParam, PageDumpConfig
from osw.wtsite import WtSite

# Create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)

# login to demo.open-semantic-lab.org
osw_obj = OSW(
    site=WtSite(
        WtSite.WtSiteConfig(
            iri="demo.open-semantic-lab.org",
            cred_mngr=CredentialManager(cred_filepath=pwd_file_path),
        )
    )
)

# download all pages in a PagePackage
# pages = wiki_tools.semantic_search(
# osw_obj.site._site,
# "[[Category:Entity]] OR [[:Category:+]]
# )
# only classes
pages = wiki_tools.semantic_search(osw_obj.site._site, "[[HasType::Category:Category]]")
print(f"Found {len(pages)} Entity pages.")
target_dir = Path("osw_files") / "packages" / "local.offline"
package = osw_obj.site.create_page_package(
    CreatePagePackageParam(
        config=PagePackageConfig(
            name="local.offline",
            config_path=target_dir / "package.json",
            content_path=target_dir,  # / "content",
            titles=pages,
            bundle=PagePackageBundle(
                packages={
                    "local.offline": PagePackage(
                        globalID="local.offline",
                        description="Offline OSW package example",
                        version="0.1.0",
                        baseURL="http://local.offline",
                    )
                }
            ),
        ),
        dump_config=PageDumpConfig(target_dir=target_dir),
    )
)

# load pages from local offline package
offline_pages = {}
result = osw_obj.site.read_page_package(
    WtSite.ReadPagePackageParam(
        storage_path=target_dir,
    )
)
offline_pages = {page.title: page for page in result.pages}
print(offline_pages["Category:Category"])
res = osw_obj.load_entity(
    OSW.LoadEntityParam(titles=pages, offline_pages=offline_pages)
)

result = osw_obj.export_jsonld(
    params=OSW.ExportJsonLdParams(
        entities=res.entities,
        mode=OSW.JsonLdMode.expand,
        build_rdf_graph=True,
        context_loader_config=WtSite.JsonLdContextLoaderParams(
            prefer_external_vocal=False, offline_pages=offline_pages
        ),
    )
)

graph = result.graph
# all triples in the graph
qres = graph.query(
    """
    SELECT ?s ?p ?o
    WHERE {
    ?s ?p ?o .
    }
    """
)
# Count triples
print(f"\nTotal triples in the graph: {len(qres)}")

# query all properties of Category:Item
qres = graph.query(
    """
    SELECT ?property ?object
    WHERE {
    Category:Item ?property ?object .
    }
    """
)
print("\nProperties of Category:Item:")
for row in qres:
    print(row.property, row.object)
