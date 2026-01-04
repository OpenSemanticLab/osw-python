import os

from osw.auth import CredentialManager
from osw.core import model
from osw.express import OswExpress
from osw.ontology import ImportConfig, OntologyImporter, ParserSettings

# Use credentials from file. if none are found, the user will be prompted to enter them
cm = CredentialManager(
    cred_filepath=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
    )
)
# Create the OSW object
# Set a local password in you user settings when using SSO login (e.g. ORCID)
osw_obj = OswExpress(domain="demo.open-semantic-lab.org", cred_mngr=cm)
# Load the required schemas / data classes
DEPENDENCIES = {
    # "OwlClass": "Category:OSW725a3cf5458f4daea86615fcbd0029f8",
    "OwlIndividual": "Category:OSW6b9ef2784a934b8ab96523366e23e906",
    "OwlOntology": "Category:OSW662db0a2ad0946148422245f84e82f64",
    "EmmoClass": "Category:OSW57beed5e1294434ba77bb6516e461456",
    "Item": "Category:Item",
    "ObjectProperty": "Category:ObjectProperty",
    "DataProperty": "Category:DataProperty",
    "AnnotationProperty": "Category:AnnotationProperty",
}
osw_obj.install_dependencies(DEPENDENCIES, mode="append")  # , policy="if-missing")

ontology_name = "MWO"

# Define ontology metadata
mwo = model.OwlOntology(
    name="MWO",
    label=[model.Label(text="MWO", lang="en")],
    iri="http://purls.helmholtz-metadaten.de/mwo",
    prefix="http://purls.helmholtz-metadaten.de/mwo/",
    prefix_name="mwo",
    see_also=["https://ise-fizkarlsruhe.github.io/mwo"],
)
pmdco = model.OwlOntology(
    name="PMDco",
    label=[model.Label(text="PMDco", lang="en")],
    iri="https://w3id.org/pmd/co",
    prefix="https://w3id.org/pmd/co/",
    prefix_name="pmdco",
    see_also=["https://w3id.org/pmd/co"],
)
nfdi = model.OwlOntology(
    name="NFDI",
    label=[model.Label(text="NFDI Ontology", lang="en")],
    iri="https://nfdi.fiz-karlsruhe.de/ontology",
    prefix="https://nfdi.fiz-karlsruhe.de/ontology/",
    prefix_name="nfdicore",
    see_also=["https://nfdi.fiz-karlsruhe.de/ontology"],
)
owl = model.OwlOntology(
    name="OWL",
    label=[model.Label(text="Web Ontology Language", lang="en")],
    iri="http://www.w3.org/2002/07/owl",
    prefix="http://www.w3.org/2002/07/owl#",
    prefix_name="owl",
    see_also=["http://www.w3.org/2002/07/owl"],
)
schema = model.OwlOntology(
    name="Schema.org",
    label=[model.Label(text="Schema.org", lang="en")],
    iri="http://schema.org/",
    prefix="http://schema.org/",
    prefix_name="schema",
    see_also=["http://schema.org/"],
)
skos = model.OwlOntology(
    name="SKOS",
    label=[model.Label(text="Simple Knowledge Organization System", lang="en")],
    iri="http://www.w3.org/2004/02/skos/core",
    prefix="http://www.w3.org/2004/02/skos/core#",
    prefix_name="skos",
    see_also=["http://www.w3.org/2004/02/skos/core"],
)
foaf = model.OwlOntology(
    name="FOAF",
    label=[model.Label(text="Friend of a Friend", lang="en")],
    iri="http://xmlns.com/foaf/0.1/",
    prefix="http://xmlns.com/foaf/0.1/",
    prefix_name="foaf",
    see_also=["http://xmlns.com/foaf/0.1/"],
)
dc = model.OwlOntology(
    name="DC",
    label=[model.Label(text="Dublin Core", lang="en")],
    iri="http://purl.org/dc/elements/1.1",
    prefix="http://purl.org/dc/elements/1.1/",
    prefix_name="dc",
    see_also=["http://purl.org/dc"],
)
bibo = model.OwlOntology(
    name="BIBO",
    label=[model.Label(text="The Bibliographic Ontology", lang="en")],
    iri="http://purl.org/ontology/bibo/",
    prefix="http://purl.org/ontology/bibo/",
    prefix_name="bibo",
    see_also=["http://purl.org/ontology/bibo/"],
)
vann = model.OwlOntology(
    name="VANN",
    label=[model.Label(text="Vocabulary Annotation", lang="en")],
    iri="http://purl.org/vocab/vann/",
    prefix="http://purl.org/vocab/vann/",
    prefix_name="vann",
    see_also=["http://purl.org/vocab/vann/"],
)
adms = model.OwlOntology(
    name="ADMS",
    label=[model.Label(text="ADMS Ontology", lang="en")],
    iri="http://www.w3.org/ns/adms",
    prefix="http://www.w3.org/ns/adms#",
    prefix_name="adms",
    see_also=["http://www.w3.org/ns/adms#"],
)
dcat = model.OwlOntology(
    name="DCAT",
    label=[model.Label(text="Data Catalog Vocabulary", lang="en")],
    iri="http://www.w3.org/ns/dcat",
    prefix="http://www.w3.org/ns/dcat#",
    prefix_name="dcat",
    see_also=["http://www.w3.org/ns/dcat#"],
)
dcterms = model.OwlOntology(
    name="DCTerms",
    label=[model.Label(text="Dublin Core Terms", lang="en")],
    iri="http://purl.org/dc/terms",
    prefix="http://purl.org/dc/terms/",
    prefix_name="dct",
    see_also=["http://purl.org/dc/terms"],
)
doap = model.OwlOntology(
    name="DOAP",
    label=[model.Label(text="Description of a Project", lang="en")],
    iri="http://usefulinc.com/ns/doap",
    prefix="http://usefulinc.com/ns/doap#",
    prefix_name="doap",
    see_also=["http://usefulinc.com/ns/doap"],
)
edam = model.OwlOntology(
    name="EDAM",
    label=[model.Label(text="EDAM Ontology", lang="en")],
    iri="http://edamontology.org",
    prefix="http://edamontology.org/",
    prefix_name="edam",
    see_also=["http://edamontology.org"],
)
edam_obo = model.OwlOntology(
    name="EDAM-OBO",
    label=[model.Label(text="EDAM Ontology (OBO)", lang="en")],
    iri="http://purl.obolibrary.org/obo/edam",
    prefix="http://purl.obolibrary.org/obo/edam#",
    prefix_name="edamobo",
    see_also=["http://edamontology.org"],
)
bfo = model.OwlOntology(
    name="BFO",
    label=[model.Label(text="Basic Formal Ontology", lang="en")],
    iri="http://purl.obolibrary.org/obo/",
    prefix="http://purl.obolibrary.org/obo/BFO_",
    prefix_name="bfo",
    see_also=["http://purl.obolibrary.org/obo/bfo"],
)
iao = model.OwlOntology(
    name="IAO",
    label=[model.Label(text="Information Artifact Ontology", lang="en")],
    iri="http://purl.obolibrary.org/obo/",
    prefix="http://purl.obolibrary.org/obo/IAO_",
    prefix_name="iao",
    see_also=["http://purl.obolibrary.org/obo/iao"],
)
omo = model.OwlOntology(
    name="OMO",
    label=[model.Label(text="Ontology for Media Objects", lang="en")],
    iri="http://purl.obolibrary.org/obo/",
    prefix="http://purl.obolibrary.org/obo/OMO_",
    prefix_name="omo",
    see_also=["http://purl.obolibrary.org/obo/omo"],
)
swo = model.OwlOntology(
    name="SWO",
    label=[model.Label(text="Software Ontology", lang="en")],
    iri="http://ebi.ac.uk/swo",
    prefix="http://ebi.ac.uk/swo/",
    prefix_name="swo",
    see_also=["http://ebi.ac.uk/swo/"],
)
obo_in_owl = model.OwlOntology(
    name="OBOInOWL",
    label=[model.Label(text="OBO In OWL", lang="en")],
    iri="http://www.geneontology.org/formats/oboInOwl",
    prefix="http://www.geneontology.org/formats/oboInOwl#",
    prefix_name="obo_in_owl",
    see_also=["http://www.geneontology.org/formats/oboInOwl"],
)
rdfs = model.OwlOntology(
    name="RDFS",
    label=[model.Label(text="RDF Schema", lang="en")],
    iri="http://www.w3.org/2000/01/rdf-schema",
    prefix="http://www.w3.org/2000/01/rdf-schema#",
    prefix_name="rdfs",
    see_also=["http://www.w3.org/2000/01/rdf-schema"],
)

import_config = ImportConfig(
    ontology_name=ontology_name,
    ontologies=[
        mwo,
        pmdco,
        nfdi,
        owl,
        schema,
        skos,
        foaf,
        dc,
        bibo,
        vann,
        adms,
        dcat,
        dcterms,
        doap,
        edam,
        edam_obo,
        bfo,
        obo_in_owl,
        rdfs,
        iao,
        omo,
        swo,
    ],
    file="https://raw.githubusercontent.com/ISE-FIZKarlsruhe/mwo/refs/heads/main/mwo.ttl",
    base_class=model.OwlClass,
    base_class_title="Category:OSW725a3cf5458f4daea86615fcbd0029f8",  # OwlClass
    dump_files=True,
    dump_path=os.path.dirname(os.path.abspath(__file__)),
    dry_run=False,
    change_id="84b563ec-4fd4-41da-8038-9cc4891fde85",
)
parser_settings = ParserSettings()
parser_settings.ensure_array.append("elucidation")
parser_settings.ensure_multilang.append("elucidation")

# Import ontologies
importer = OntologyImporter(osw=osw_obj, parser_settings=parser_settings)
prefix_dict = importer.import_ontology(import_config)
