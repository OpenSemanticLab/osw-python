import os

from osw.auth import CredentialManager
from osw.core import OSW, model
from osw.ontology import ImportConfig, OntologyImporter
from osw.wtsite import WtSite

# use credentials from file. if none are found, the user will be prompted to enter them
cm = CredentialManager(
    cred_filepath=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
    )
)

# create the site object
wtsite = WtSite(
    WtSite.WtSiteConfig(iri="https://wiki-dev.open-semantic-lab.org", cred_mngr=cm)
)
osw = OSW(site=wtsite)

list_of_schemas = [
    "Category:OSW725a3cf5458f4daea86615fcbd0029f8",  # OwlClass
    "Category:OSW6b9ef2784a934b8ab96523366e23e906",  # OwlIndividual
    "Category:Item",
    "Category:ObjectProperty",
    "Category:DataProperty",
    "Category:AnnotationProperty",
]
for i, cat in enumerate(list_of_schemas):
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
        os.path.dirname(os.path.abspath(__file__)), "data", f"{ontology_name}.ttl"
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
