import datetime
import io
import json
import os
import zipfile
from pprint import pprint
from typing import List, Optional
from uuid import UUID, uuid5

from pyld import jsonld

import osw.model.entity as model
from osw.core import OSW
from osw.express import OswExpress
from osw.utils.wiki import get_full_title

# Create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "accounts.pwd.yaml"
)
# pwd_file_path = "./accounts.pwd.yaml"
osw_obj = OswExpress(
    domain="wiki-dev.open-semantic-lab.org", cred_filepath=pwd_file_path
)

# load dependencies
DEPENDENCIES = {
    "ElnEntry": "Category:OSW0e7fab2262fb4427ad0fa454bc868a0d",
    # "Location": "Category:OSW3d238d05316e45a4ac95a11d7b24e36b",
    # "Device": "Category:OSWf0fe562f422d49c6877490b3dfee2f3f",
    "Organization": "Category:OSW1969007d5acf40539642877659a02c23",
    "WikiFile": "Category:OSW11a53cdfbdc24524bf8ac435cbf65d9d",
    "Person": "Category:OSW44deaa5b806d41a2a88594f562b110e9",
    "CreativeWork": "Category:OSW712583f2479944deb2546b77cf860dda",
    "Keyword": "Category:OSW09f6cdd54bc54de786eafced5f675cbe",
}
osw_obj.install_dependencies(DEPENDENCIES, mode="append", policy="if-missing")

# define test namespace to create persistent UUIDs
TEST_UUID_NAMESPACE = UUID("23e4356e-b726-4c5b-b63a-620b304eb836")


class RoCreateRoot(model.CreativeWork):
    id: Optional[str] = "ro-crate-metadata.json"
    rdf_type: Optional[List[str]] = ["schema:CreativeWork"]
    about: Optional[List[str]] = ["./"]
    conforms_to: Optional[List[str]] = ["https://w3id.org/ro/crate/1.1"]
    date_created: Optional[datetime.datetime] = datetime.datetime.now()
    publisher: Optional[List[str]] = None
    version: Optional[str] = "1.0"


class RoCreateRootDataset(model.Data):
    id: Optional[str] = "./"
    rdf_type: Optional[List[str]] = ["schema:Dataset"]
    has_part: Optional[List[str]] = []
    license: Optional[List[str]] = ["https://creativecommons.org/licenses/by/4.0/"]
    date_published: Optional[datetime.datetime] = datetime.datetime.now()


class RoCrateElnEntry(model.ElnEntry):
    id: str
    """local id, equals subdirectory name"""


o = model.Organization(
    uuid=uuid5(TEST_UUID_NAMESPACE, "OpenSemanticLab"),
    rdf_type=["schema:Organization"],
    name="OpenSemanticLab",
    label=[model.Label(text="OpenSemanticLab")],
    # description=[model.Description(text="OpenSemanticLab")],
    website=["https://github.com/OpenSemanticLab"],
)

p = model.Person(
    uuid=uuid5(TEST_UUID_NAMESPACE, "TestPerson"),
    rdf_type=["schema:Person"],
    name="TestPerson",
    first_name="Test",
    surname="Person",
    label=[model.Label(text="Test Person")],
    email=["test@example.com"],
)

e = RoCrateElnEntry(
    uuid=uuid5(TEST_UUID_NAMESPACE, "MinimalExample"),
    id="./TestEntry/",
    rdf_type=["schema:Dataset"],
    name="MinimalExample",
    label=[model.Label(text="Minimal Example")],
    description=[
        model.Description(text="A minimal test dataset exported from OpenSemanticLab")
    ],
    start_date_time="2021-01-01T00:00:00Z",
    end_date_time="2021-01-02T00:00:00Z",
    creator=get_full_title(p),
)

c = RoCreateRoot(
    uuid=uuid5(TEST_UUID_NAMESPACE, "RootEntry"),
    name="RootEntry",
    label=[model.Label(text="Root Entry")],
    description=[model.Description(text="Root Entry")],
    publisher=[get_full_title(o)],
    date_created="2021-01-01T00:00:00Z",
)

rd = RoCreateRootDataset(
    uuid=uuid5(TEST_UUID_NAMESPACE, e.name + "./"),
    name=e.name,
    label=e.label,
    description=e.description,
    date_published="2021-01-01T00:00:00Z",
)

rd.has_part.append(e.id)

# data = json.loads(e.json(exclude_none=True, indent=4, ensure_ascii=False))
# data["@context"] = "/wiki/Category:OSW0e7fab2262fb4427ad0fa454bc868a0d"
# data = jsonld.expand(data)
context = [
    "https://w3id.org/ro/crate/1.1/context",
    {
        # "type": "@type",
        # "rdf_type": "@type",
        "type": {"@id": "schema:additionalType", "@type": "@id"},
        "rdf_type": "@type",
        "description": {
            "@id": "schema:description",
            "@context": {
                "text": "@value",
                "lang": "@lang",
            },
        },
        # - root
        "about": {"@id": "schema:about", "@type": "@id"},
        "conforms_to": {"@id": "conformsTo", "@type": "@id"},
        "date_created": "dateCreated",
        "publisher": {"@id": "schema:sdPublisher", "@type": "@id"},
        "date_published": "schema:datePublished",
        # "license": {"@id": "schema:license", "@type": "@id"},
        # - Dataset
        "has_part": {"@id": "schema:hasPart", "@type": "@id", "@container": "@set"},
        "start_date_time": "schema:dateCreated",
        "creator": {"@id": "schema:author", "@type": "@id"},
        # - Organization
        "website": "url",
    },
]
res = osw_obj.export_jsonld(
    params=OSW.ExportJsonLdParams(
        entities=[c, rd, o, p, e],
        id_keys=["osw_id", "id", "iri"],
        mode=OSW.JsonLdMode.expand,
        build_rdf_graph=True,
        context=context,
    )
)
pprint(res.documents)

rocreate_jsonld = jsonld.flatten(
    res.graph_document,
    [
        "https://w3id.org/ro/crate/1.1/context",
        {"hasPart": {"@id": "schema:hasPart", "@type": "@id", "@container": "@set"}},
    ],
    # {"compactArrays": False, "graph": True}
)
rocreate_jsonld["@context"] = "https://w3id.org/ro/crate/1.1/context"

# rocreate enforces explicit subobjects with "@id" key
# find all nodes in the @graph with hasPart property
# make sure to map 'iri' to {'@id': 'iri'}
for node in rocreate_jsonld["@graph"]:
    if "hasPart" in node:
        node["hasPart"] = [{"@id": part} for part in node["hasPart"]]

# order the nodes in the @graph
# "@id": "ro-crate-metadata.json" first
# "@id": "./" second
# all other nodes by their "@id" in alphabetical order


def sort_key(node):
    if node.get("@id") == "ro-crate-metadata.json":
        return "0"
    if node.get("@id") == "./":
        return "1"
    return "2" + node.get("@id")


rocreate_jsonld["@graph"] = sorted(rocreate_jsonld["@graph"], key=sort_key)


pprint(rocreate_jsonld)

# save as ro-crate-metadata.json within zip file with rd.name as file name
zip_buffer = io.BytesIO()

with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
    zip_file.writestr(
        f"{rd.name}/ro-crate-metadata.json",
        json.dumps(rocreate_jsonld, indent=4, ensure_ascii=False),
    )

target_dir = ""
with open(target_dir + f"{rd.name}.json", "w") as f:
    json.dump(rocreate_jsonld, f, indent=4, ensure_ascii=False)
with open(target_dir + f"{rd.name}.zip", "wb") as f:
    f.write(zip_buffer.getvalue())
with open(target_dir + f"{rd.name}.osl.eln", "wb") as f:
    f.write(zip_buffer.getvalue())
