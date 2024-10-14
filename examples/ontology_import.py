import os

from osw.auth import CredentialManager
from osw.core import model
from osw.express import OswExpress
from osw.ontology import ImportConfig, OntologyImporter

# Use credentials from file. if none are found, the user will be prompted to enter them
cm = CredentialManager(
    cred_filepath=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
    )
)

# Create the OSW object
osw_obj = OswExpress(domain="wiki-dev.open-semantic-lab.org", cred_mngr=cm)

DEPENDENCIES = {
    "OwlClass": "Category:OSW725a3cf5458f4daea86615fcbd0029f8",
    "OwlIndividual": "Category:OSW6b9ef2784a934b8ab96523366e23e906",
    "Item": "Category:Item",
    "ObjectProperty": "Category:ObjectProperty",
    "DataProperty": "Category:DataProperty",
    "AnnotationProperty": "Category:AnnotationProperty",
}
osw_obj.install_dependencies(DEPENDENCIES, mode="append")

ontology_name = "example_ontology"

ex = model.OwlOntology(
    name="Example",
    label=[model.Label(text="Example", lang="en")],
    iri="http://example.com",
    prefix="http://example.com/",
    prefix_name="example",
    see_also=["http://example.com"],
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

# Import ontologies
importer = OntologyImporter(
    osw=osw_obj,
)
importer.import_ontology(import_config)
