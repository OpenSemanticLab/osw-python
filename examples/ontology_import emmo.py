import os

from osw.auth import CredentialManager
from osw.core import OSW, model
from osw.ontology import ImportConfig, OntologyImporter, ParserSettings
from osw.wtsite import WtSite

# use credentials from file. if none are found, the user will be prompted to enter them
cm = CredentialManager(
    cred_filepath=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
    )
)

# create the site object
wtsite = WtSite(WtSite.WtSiteConfig(iri="http://<your-instance>:18081", cred_mngr=cm))
osw = OSW(site=wtsite)

list_of_schemas = [
    "Category:OSW725a3cf5458f4daea86615fcbd0029f8",  # OwlClass
    "Category:OSW6b9ef2784a934b8ab96523366e23e906",  # OwlIndividual
    "Category:OSW57beed5e1294434ba77bb6516e461456",  # EmmoClass
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

ontology_name = "BVCO"

# define ontology metadata
emmo = model.Ontology(
    name="EMMO",
    iri="http://emmo.info/emmo",
    prefix="http://emmo.info/emmo#",
    prefix_name="emmo",
    link="https://github.com/emmo-repo/EMMO",
)
dc = model.Ontology(
    name="DC",
    iri="http://purl.org/dc/elements/1.1",
    prefix="http://purl.org/dc/elements/1.1/",
    prefix_name="dc",
    link="http://purl.org/dc",
)
battinfo = model.Ontology(
    name="EMMO BattINFO",
    iri="http://emmo.info/battery",
    prefix="http://emmo.info/battery#",
    prefix_name="battinfo",
    link="https://github.com/BIG-MAP/BattINFO",
)
electrochemistry = model.Ontology(
    name="EMMO Electrochemistry",
    iri="http://emmo.info/electrochemistry",
    prefix="http://emmo.info/electrochemistry#",
    prefix_name="electrochemistry",
    link="https://github.com/emmo-repo/EMMO",
)
periodictable = model.Ontology(
    name="EMMO Periodic Table",
    iri="http://emmo.info/emmo/domain/periodic-table",
    prefix="http://emmo.info/emmo/domain/periodic-table#",
    prefix_name="periodictable",
    link="https://github.com/emmo-repo/EMMO",
)
gpo = model.Ontology(
    name="GPO",
    iri="https://gpo.ontology.link",
    prefix="https://gpo.ontology.link/",
    prefix_name="gpo",
    link="https://github.com/General-Process-Ontology/ontology",
)
bvco = model.Ontology(
    name="BVCO",
    iri="https://bvco.ontology.link",
    prefix="https://bvco.ontology.link/",
    prefix_name="bvco",
    link="https://github.com/Battery-Value-Chain-Ontology/ontology",
)

import_config = ImportConfig(
    ontology_name=ontology_name,
    ontologies=[emmo, dc, battinfo, electrochemistry, periodictable, gpo, bvco],
    # file="https://raw.githubusercontent.com/BIG-MAP/BattINFO/master/battinfo.ttl",
    file="https://raw.githubusercontent.com/emmo-repo/domain-battery/master/battery.ttl",
    base_class=model.EmmoClass,
    base_class_title="Category:OSW57beed5e1294434ba77bb6516e461456",  # EmmoClass
    dump_files=True,
    dump_path=os.path.dirname(os.path.abspath(__file__)),
    dry_run=False,
)
parser_settings = ParserSettings()
parser_settings.ensure_array.append("elucidation")
parser_settings.ensure_multilang.append("elucidation")

# import ontologies
importer = OntologyImporter(osw=osw, parser_settings=parser_settings)
importer.import_ontology(import_config)
