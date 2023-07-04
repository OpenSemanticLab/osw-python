import json

# import os
import re
from uuid import UUID

import mwclient
from pyld import jsonld
from rdflib import Graph

import osw.model.entity as model

# from osw.auth import CredentialManager
from osw.core import OSW
from osw.wtsite import WtSite

# create/update the password file under examples/accounts.pwd.yaml
# pwd_file_path = os.path.join(
#     os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
# )
# cm = CredentialManager(cred_filepath=pwd_file_path)
# wtsite = WtSite(WtSite.WtSiteConfig(
#     iri="http://localhost:18081",
#     cred_mngr=cm
# ))

# or use a hardocded login
site = mwclient.Site(scheme="http", host="localhost:18081", path="/w/")
site.login("Admin", "change_me123123")
wtsite = WtSite(WtSite.WtSiteLegacyConfig(site=site))

osw = OSW(site=wtsite)


# load the EmmoTerm schema => run the script a second time after the schema was loaded
try:
    model.EmmoTerm
except AttributeError:
    # name 'EmmoTerm' is not defined
    osw.fetch_schema(
        osw.FetchSchemaParam(
            schema_title="Category:OSW57beed5e1294434ba77bb6516e461456",
            mode="replace",  # EmmoTerm
        )
    )

# load the ontology
g = Graph()
g.parse(
    "https://raw.githubusercontent.com/emmo-repo/domain-battery/master/battery.ttl",
    format="n3",
)
# g.parse("https://github.com/Battery-Value-Chain-Ontology/ontology/releases/download/v0.3.0/BVCO_inferred.ttl", format="n3")
# g.parse(r"BVCO_inferred.ttl")

# convert to json-ld dict
g = json.loads(g.serialize(format="json-ld", auto_compact=True))

# define the context
context = {
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "dc": "http://purl.org/dc/terms/",
    "emmo": "http://emmo.info/emmo#",  # keep values with full uri
    "uri": {"@id": "@id"},
    "rdf_type": {"@id": "@type"},
    # "label": "rdfs:label",
    "label": {"@id": "skos:prefLabel"},
    "altLabel": {"@id": "skos:altLabel"},
    "text": {"@id": "@value"},
    "lang": {"@id": "@language"},
    "subclass_of": {"@id": "rdfs:subClassOf", "@type": "@id"},
    "source": "dc:source",
    "disjointUnionOf": "owl:disjointUnionOf",
    "disjointWith": "owl:disjointWith",
    "equivalentClass": "owl:equivalentClass",
    "unionOf": {"@id": "owl:unionOf", "@container": "@list", "@type": "@id"},
    "comment": "rdfs:comment",
    "isDefinedBy": "rdfs:isDefinedBy",
    "seeAlso": "rdfs:seeAlso",
    # shorten properties
    "qudtReference": "http://emmo.info/emmo#EMMO_1f1b164d_ec6a_4faa_8d5e_88bda62316cc",
    "omReference": "http://emmo.info/emmo#EMMO_209ba1b3_149f_4ff0_b672_941610eafd72",
    "wikidataReference": "http://emmo.info/emmo#EMMO_26bf1bef_d192_4da6_b0eb_d2209698fb54",
    "ISO9000Reference": "http://emmo.info/emmo#EMMO_3aa37f92_8dc5_4ee4_8438_e41e6ae20c62",
    "IEVReference": "http://emmo.info/emmo#EMMO_50c298c2_55a2_4068_b3ac_4e948c33181f",
    "dbpediaReference": "http://emmo.info/emmo#EMMO_6dd685dd_1895_46e4_b227_be9f7d643c25",
    "etymology": "http://emmo.info/emmo#EMMO_705f27ae_954c_4f13_98aa_18473fc52b25",
    "definition": "http://emmo.info/emmo#EMMO_70fe84ff_99b6_4206_a9fc_9a8931836d84",
    "ISO80000Reference": "http://emmo.info/emmo#EMMO_8de5d5bf_db1c_40ac_b698_095ba3b18578",
    "ISO14040Reference": "http://emmo.info/emmo#EMMO_964568dd_64d2_454b_a12f_ac389f1c5e7f",
    "description": "http://emmo.info/emmo#EMMO_967080e5_2f42_4eb2_a3a9_c58143e835f9",  # elucidation
    "example": "http://emmo.info/emmo#EMMO_b432d2d5_25f4_4165_99c5_5935a7763c1a",
    "VIMTerm": "http://emmo.info/emmo#EMMO_bb49844b_45d7_4f0d_8cae_8e552cbc20d6",
    "emmo_comment": "http://emmo.info/emmo#EMMO_c7b62dd7_063a_4c2a_8504_42f7264ba83f",
    "wikipediaReference": "http://emmo.info/emmo#EMMO_c84c6752_6d64_48cc_9500_e54a3c34898d",
    "iupacReference": "http://emmo.info/emmo#EMMO_fe015383_afb3_44a6_ae86_043628697aa2",
}

# compact the json-ld (replace IRIs defined in the context with plain properties)
compacted = jsonld.compact(g, context)

# define postprocessed properties
ensure_multilang = ["label", "prefLabel", "altLabel", "comment", "description"]
ensure_array = [
    "label",
    "prefLabel",
    "altLabel",
    "comment",
    "description",
    "subclass_of",
]
map_uuid_uri = ["subclass_of"]
remove_unnamed = ["subclass_of"]  # , 'equivalentClass']

# postprocess json-ld
for node in compacted["@graph"]:
    for key in ensure_multilang:
        if key in node:
            if isinstance(node[key], str):
                node[key] = {"text": node[key], "lang": "en"}
            elif "text" in node[key] and "lang" not in node[key]:
                node[key]["lang"] = "en"
            elif isinstance(node[key], list):
                for i, val in enumerate(node[key]):
                    if isinstance(node[key][i], str):
                        node[key][i] = {"text": node[key][i], "lang": "en"}
                    elif "text" in node[key][i] and "lang" not in node[key][i]:
                        node[key][i]["lang"] = "en"
    for key in ensure_array:
        if key in node and not isinstance(node[key], list):
            node[key] = [node[key]]
    for key in remove_unnamed:
        if key in node:
            if isinstance(node[key], list):
                node[key] = [value for value in node[key] if not value.startswith("_:")]
            elif isinstance(node[key], str) and node[key].startswith("_:"):
                del node[key]
    for key in map_uuid_uri:
        if key in node:
            if isinstance(node[key], list):
                for i, val in enumerate(node[key]):
                    node[key][i] = "Category:OSW" + str(
                        UUID(re.sub(r"[^A-Fa-f0-9]", "", node[key][i])[-32:])
                    ).replace("-", "")
            if isinstance(node[key], str):
                node[key][i] = "Category:OSW" + str(
                    UUID(re.sub(r"[^A-Fa-f0-9]", "", node[key][i])[-32:])
                ).replace("-", "")

    if (
        "rdf_type" in node
        and node["rdf_type"] == "owl:Class"
        and not node["uri"].startswith("_:")
    ):
        node["uuid"] = str(UUID(re.sub(r"[^A-Fa-f0-9]", "", node["uri"])[-32:]))

        if "prefLabel" in node:
            node["name"] = node["prefLabel"][0]["text"]
        elif "label" in node:
            node["name"] = node["label"][0]["text"]
        else:
            print("No label: ", node["uri"])

# store the json-ld serialization on disk
with open("BVCO.compacted.jsonld", "w", encoding="utf-8") as f:
    json.dump(compacted, f, indent=4, ensure_ascii=False)

# optional: also serialize as ttl
g2 = Graph()
g2.parse("BVCO.compacted.jsonld")
g2.serialize(destination="BVCO.jsonld.ttl", format="ttl")

# create OSW entities
limit = 3000  # choose a smaller number for tests
counter = 0
max_index = len(compacted["@graph"])
entities = []
for index, node in enumerate(compacted["@graph"]):
    if "rdf_type" in node and node["rdf_type"] == "owl:Class":
        if "label" in node:
            if counter < limit:
                e = model.EmmoTerm(**node)
                entities.append(e)
                counter += 1

# define ontology metadata
emmo = model.Ontology(
    name="EMMO",
    iri="http://emmo.info/emmo",
    prefix="http://emmo.info/emmo#",
    prefix_name="emmo",
    link="https://github.com/emmo-repo/EMMO",
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

ontologies = [emmo, battinfo, electrochemistry, periodictable, gpo, bvco]
# ontologies = [battinfo]

# import ontologies
osw.import_ontology(OSW.ImportOntologyParam(ontologies=ontologies, entities=entities))
