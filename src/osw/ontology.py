import json
import os
import re
import uuid
from typing import Dict, List, Literal, Optional

import pyld
from pydantic import PrivateAttr
from pydantic.main import ModelMetaclass
from pyld import jsonld
from rdflib import Graph
from typing_extensions import deprecated

from osw.core import OSW, model
from osw.model.static import OswBaseModel
from osw.utils.strings import pascal_case
from osw.utils.wiki import get_namespace
from osw.wtsite import WtSite


class ParserSettings(OswBaseModel):
    """Settings for the ontology parser"""

    flatten_subclassof_restrictions: Optional[bool] = False
    """If True, the parser will directly asign the property and the value class of the restriction to the restricted class
    """
    subclassof_restrictions_keyword: Optional[str] = "restrictions"
    """Keyword to separate the owl restrictions from rdfs subclassof. Only used if flatten_subclassof_restrictions is False."""
    ensure_multilang: Optional[List[str]] = [
        "label",
        "prefLabel",
        "altLabel",
        "comment",
        "description",
    ]
    """List of properties that should be multilang / have a @lang containter. If the property is not multilang, the parser will create a multilang property with "en" as default language."""
    ensure_array: Optional[List[str]] = [
        "rdf_type",
        "label",
        "prefLabel",
        "altLabel",
        "comment",
        "description",
        "subclass_of",
        "restrictions",
    ]
    """List of properties that should be arrays. If the property is not an array, the parser will create an array with the value as single element."""
    map_uuid_iri: Optional[List[str]] = [
        "subclass_of",
        "on_property",
        "some_values_from",
        "all_values_from",
        "domain",
        "range",
        "subproperty_of",
    ]
    """List of properties whose values should be mapped to (OSW) UUIDs. If the value is not a UUID, the parser will create a UUIDv5 from the value with the URL namespace."""
    remove_unnamed: Optional[List[str]] = []  # ['subclass_of'] #, 'equivalentClass']
    """List of properties whose values should be removed if they are unnamed nodes ("_:...")"""


class ImportConfig(OswBaseModel):
    """Configuration for the ontology importer"""

    file: str
    """the path or url to the ontology file"""
    file_format: Literal["xml", "n3", "nt", "trix"] = "n3"
    """the serialization format. for turtle, use 'n3' (see rdflib docs)"""
    ontology_name: str
    """the name of the ontology"""
    ontologies: List[model.Ontology]
    """Ontology metadata, inluding imported ontologies"""
    import_mapping: Optional[Dict[str, str]] = {}
    """Mapping of imported ontologies iri to their resolveable file url in case both are not identical"""
    base_class: ModelMetaclass
    """Base class for the ontology model. For OWL Ontologies, this should be model.OwlClass or a subclass of it."""
    base_class_title: Optional[
        str
    ] = "Category:OSW725a3cf5458f4daea86615fcbd0029f8"  # OwlClass
    """Title of the base class schema. Defaults to OwlClass"""
    meta_class_title: Optional[
        str
    ] = "Category:OSW379d5a1589c74c82bc0de47938264d00"  # OwlThing
    """Title of the meta class schema. Defaults to OwlThing"""
    dump_files: Optional[bool] = False
    """If True, the parsed ontology will be dumped to a jsonld file"""
    dump_path: Optional[str] = None
    """Path to the directory where the parsed ontology will be dumped"""
    dry_run: Optional[bool] = False
    """If True, the parsed ontology will not be imported into the wiki"""
    property_naming_policy: Optional[
        Literal["UUID", "label", "prefixed_label"]
    ] = "prefixed_label"
    """Policy for naming properties. If "UUID", the property will be named with a UUIDv5.
    If "label", the property will be named with the label of the property.
    If "prefixed_label", the property will be named with the label of the property prefixed with the label of the ontology."""
    property_naming_prefix_delimiter: Optional[str] = ":"
    """Delimiter for the prefixed_label property naming policy"""

    class Config:
        arbitrary_types_allowed = True


class OntologyImporter(OswBaseModel):
    """Class for importing ontologies into OSW"""

    osw: OSW
    """A OSW instance"""
    parser_settings: Optional[ParserSettings] = ParserSettings()
    """Settings for the ontology parser"""
    import_config: Optional[ImportConfig] = None
    """Configuration for the ontology importer"""

    _context: Optional[Dict] = PrivateAttr()
    _id_dict: Optional[Dict] = PrivateAttr()
    _iri_dict: Optional[Dict] = PrivateAttr()
    _prop_dict: Optional[Dict] = PrivateAttr()
    _g: Optional[Dict] = PrivateAttr()
    _entities: Optional[List] = PrivateAttr()
    _entities_json: Optional[List] = PrivateAttr()

    _imported_ontologies: Optional[List[str]] = PrivateAttr()

    @staticmethod
    def _recursive_ontology_import(
        file, format="turtle", imported_ontologies=[], import_mapping={}
    ):
        """Recursively import ontologies from owl:imports statements in the given ontology file

        Parameters:
            file (str): path or url to the ontology file
            format (str): the serialization format (see rdflib docs)
            imported_ontologies (list): list of already imported ontologies

        Returns:
            graph (rdflib.Graph): graph of the imported ontologies"""
        rdf_graph = Graph()
        rdf_graph.parse(file, format=format)

        # load the graph into a dict
        _g = json.loads(rdf_graph.serialize(format="json-ld", auto_compact=True))

        ontologies_to_import = []

        def handle_node(node):
            if "owl:imports" in node:
                if not isinstance(node["owl:imports"], list):
                    node["owl:imports"] = [node["owl:imports"]]
                for import_ in node["owl:imports"]:
                    onto = import_["@id"]
                    if onto not in imported_ontologies:
                        if onto in import_mapping:
                            ontologies_to_import.append(import_mapping[onto])
                        else:
                            ontologies_to_import.append(onto)
                        imported_ontologies.append(onto)
                        # print(node["owl:imports"]["@id"])

        if "@graph" in _g:
            for node in _g["@graph"]:
                handle_node(node)
        else:
            handle_node(_g)

        # load the imported ontologies and merge them into the main graph
        for onto in ontologies_to_import:
            print(f"Importing {onto}")
            _rdf_graph = OntologyImporter._recursive_ontology_import(
                onto,
                format=format,
                imported_ontologies=imported_ontologies,
                import_mapping=import_mapping,
            )
            rdf_graph += _rdf_graph

        return rdf_graph

    def import_ontology(self, config: ImportConfig):
        """Imports an ontology into OSW

        Parameters
        ----------
        config
            see ImportConfig

        Returns
        -------
            None
        """

        # overwrite the default document loader to load relative context from the wiki
        def myloader(*args, **kwargs):
            requests_loader = pyld.documentloader.requests.requests_document_loader(
                *args, **kwargs
            )

            def loader(url, options={}):
                if "/wiki/" in url:
                    title = url.replace("/wiki/", "").split("?")[0]
                    page = self.osw.site.get_page(
                        WtSite.GetPageParam(titles=[title])
                    ).pages[0]
                    schema = page.get_slot_content("jsonschema")
                    if isinstance(schema, str):
                        schema = json.loads(schema)
                    doc = {
                        "contentType": "application/json",
                        "contextUrl": None,
                        "documentUrl": url,
                        "document": schema,
                    }
                    return doc

                else:
                    return requests_loader(url, options)

            return loader

        jsonld.set_document_loader(myloader())

        self.import_config = config

        # load the ontology file
        self._imported_ontologies = []
        rdf_graph = self._recursive_ontology_import(
            self.import_config.file,
            self.import_config.file_format,
            self._imported_ontologies,
            self.import_config.import_mapping,
        )

        if self.import_config.dump_files:
            rdf_graph.serialize(
                destination=os.path.join(
                    self.import_config.dump_path,
                    f"{self.import_config.ontology_name}.jsonld",
                ),
                format="json-ld",
                auto_compact=True,
            )

        # load the graph into a dict
        self._g = json.loads(rdf_graph.serialize(format="json-ld", auto_compact=True))

        def node_sort(n):
            # sort nodes by type and id
            rank = 10
            if "@type" in n:
                if "Property" in n["@type"]:
                    rank = 0
                if "Class" in n["@type"]:
                    rank = 1
            return (rank, n["@id"])

        self._g["@graph"] = sorted(self._g["@graph"], key=lambda n: node_sort(n))

        # create an id-index of all nodes
        self._id_dict = {}
        for node in self._g["@graph"]:
            if "@id" in node:
                self._id_dict[node["@id"]] = node

        # add a helper context
        self._g["@context"]["_temp_"] = "http://temp.local/"

        # normalize graph
        self._sanitize_graph()

        if self.import_config.dump_files:
            with open(
                os.path.join(
                    self.import_config.dump_path,
                    f"{self.import_config.ontology_name}.mod.jsonld",
                ),
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(self._g, f, indent=4, ensure_ascii=False)

        self._construct_context()
        self._g = jsonld.compact(self._g, self._context)

        # build an iri-index of all nodes
        # ToDo: can we reuse the id-index?
        self._iri_dict = {}
        for node in self._g["@graph"]:
            self._iri_dict[node["iri"]] = node

        self._apply_osw_structure()

        if self.import_config.dump_files:
            with open(
                os.path.join(
                    self.import_config.dump_path,
                    f"{self.import_config.ontology_name}.compacted.jsonld",
                ),
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(self._g, f, indent=4, ensure_ascii=False)

            # currently does not work with relative remote context ("/wiki/..."")
            # rdf_graph.parse(os.path.join(self.import_config.dump_path, f"{self.import_config.ontology_name}.compacted.jsonld"))
            # rdf_graph.serialize(destination=os.path.join(self.import_config.dump_path, f"{self.import_config.ontology_name}.jsonld.ttl"), format="ttl")

        self._create_entities()
        # sort list by type and iri to persist the order across runs
        # self._entities = sorted(self._entities, key=lambda e: (e.type[0], e.iri))

        if self.import_config.dump_files:
            with open(
                os.path.join(
                    self.import_config.dump_path,
                    f"{self.import_config.ontology_name}.entities.jsonld",
                ),
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(self._entities_json, f, indent=4, ensure_ascii=False)

        # import ontologies
        # self._import_ontology(OSW.ImportOntologyParam(ontologies=self.import_config.ontologies, entities=self._entities, dryrun=False))

        if not self.import_config.dry_run:
            self._store_ontologies(
                OntologyImporter.StoreOntologiesParam(
                    ontologies=self.import_config.ontologies,
                    entities=self._entities,
                )
            )

    def _sanitize_graph(self) -> None:
        ps = self.parser_settings
        # sanitize types of type object, see: https://github.com/RDFLib/rdflib/issues/1950
        for node in self._g["@graph"]:
            key = "@type"
            if key in node:
                # normalize to list
                if not isinstance(node[key], list):
                    node[key] = [node[key]]
                types = []
                for i, val in enumerate(node[key]):
                    if isinstance(val, dict):
                        if "@id" in val:
                            types.append(val["@id"])
                    else:
                        types.append(val)
                node[key] = types
            # remove 'www.' from @id
            node["@id"] = node["@id"].replace("www.", "")

            # handle subClassOf and subPropertyOf
            if "rdfs:subClassOf" in node:
                if not isinstance(node["rdfs:subClassOf"], list):
                    node["rdfs:subClassOf"] = [node["rdfs:subClassOf"]]
                for i, val in enumerate(node["rdfs:subClassOf"]):
                    id = val["@id"]
                    if id in self._id_dict:
                        superclass = self._id_dict[id]
                        if (
                            "@type" in superclass
                            and superclass["@type"] == "owl:Restriction"
                            and "owl:onProperty" in superclass
                            and "owl:someValuesFrom" in superclass
                        ):
                            if ps.flatten_subclassof_restrictions:
                                if superclass["owl:onProperty"]["@id"] not in node:
                                    node[superclass["owl:onProperty"]["@id"]] = []
                                node[superclass["owl:onProperty"]["@id"]].append(
                                    superclass["owl:someValuesFrom"]["@id"]
                                )
                            else:
                                if (
                                    "_temp_:" + ps.subclassof_restrictions_keyword
                                    not in node
                                ):
                                    node[
                                        "_temp_:" + ps.subclassof_restrictions_keyword
                                    ] = []
                                node[
                                    "_temp_:" + ps.subclassof_restrictions_keyword
                                ].append(superclass)
                            node["rdfs:subClassOf"].pop(i)
                            if id in self._g["@graph"]:
                                self._delete_node(self._g["@graph"], id)
                        # else:
                        #    print("Warning: rdfs:subClassOf is not a Restriction: ", superclass)

    def _delete_node(self, id: str, key: str = "@id") -> bool:
        """Delete a node from a graph by id

        Parameters
        ----------
        graph
            the graph (list of nodes) to delete from
        id
            the id of the node to delete
        key, optional
            the id key, by default '@id'

        Returns
        -------
            True if the node was deleted, False otherwise
        """
        graph = self._g["@graph"]
        for i, node in enumerate(graph):
            if node[key] == id:
                del graph[i]
                return True
        return False

    def _construct_context(self):
        self._context = {
            "_temp_": "http://temp.local/",
            "owl": "http://www.w3.org/2002/07/owl#",
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "skos": "http://www.w3.org/2004/02/skos/core#",
            "dc": "http://purl.org/dc/terms/",
            # "emmo": "http://emmo.info/emmo#", #keep values with full iri
            "iri": {"@id": "@id"},
            "rdf_type": {"@id": "@type"},
            "label": {"@id": "rdfs:label"},
            # "label": {"@id": "skos:prefLabel"},
            "altLabel": {"@id": "skos:altLabel"},
            "text": {"@id": "@value"},
            "lang": {"@id": "@language"},
            # "subClassOf": {"@id": "rdfs:subClassOf", "@type": "@id"},
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
            "description": "http://example.com/R7k3ssL7gUxsfWuVsXWDXYF",
            # "ObjectPropertyA": "http://example.com/REh2qNSARmKpPuwrJmr5Pu",
            "Item": "https://wiki-dev.open-semantic-lab.org/wiki",
            # "Item:OSW4db96fb7e9e0466d942bf6f17bfdc145": "emmo:EMMO_4db96fb7_e9e0_466d_942b_f6f17bfdc145",
            # "uuid": "wiki:HasUuid",
            # "name": "wiki:HasName",
            # "restrictions": {"@id": "rdfs:subClassOf", "@type": "@id"},
            "restrictions": {"@id": "_temp_:restrictions", "@type": "@id"},
            "on_property": {"@id": "owl:onProperty", "@type": "@id"},
            "some_values_from": {"@id": "owl:someValuesFrom", "@type": "@id"},
            "domain": {"@id": "rdfs:domain", "@type": "@id"},
            "range": {"@id": "rdfs:range", "@type": "@id"},
            "subproperty_of": {"@id": "rdfs:subPropertyOf", "@type": "@id"},
            # "example": "http://example.com/",
        }

        # base_class_page = self.osw.site.get_page(WtSite.GetPageParam(
        #    titles=[self.import_config.base_class_title]
        # )).pages[0]
        # schema = base_class_page.get_slot_content("jsonschema")
        # if (isinstance(schema, str)):
        #    schema = json.loads(schema)
        # self._context = schema["@context"]

        self._context = [
            f"/wiki/{self.import_config.base_class_title}?action=raw&slot=jsonschema&format=json",
            {
                "_temp_": "http://temp.local/",
                "restrictions": {"@id": "_temp_:restrictions", "@type": "@id"},
            },
        ]

    def _get_uuid_from_iri(self, iri):
        node_name = iri.split("/")[-1]
        if "#" in node_name:
            node_name = node_name.split("#")[-1]
        try:
            # try to get last 32 hex digits and convert it to uuid
            # e. g. http://emmo.info/emmo/EMMO_4db96fb7_e9e0_466d_942b_f6f17bfdc145
            node_uuid = uuid.UUID(re.sub(r"[^A-Fa-f0-9]", "", node_name)[-32:])
        except Exception:
            node_uuid = uuid.uuid5(uuid.NAMESPACE_URL, iri)
        return node_uuid

    def _get_page_name(self, node):
        ns = ""
        title = ""

        node_uuid = self._get_uuid_from_iri(node["iri"])

        if "rdf_type" in node:
            if "owl:Class" in node["rdf_type"]:
                ns = "Category"
                title = OSW.get_osw_id(node_uuid)
            elif (
                "owl:ObjectProperty" in node["rdf_type"]
                or "owl:DatatypeProperty" in node["rdf_type"]
                or "owl:AnnotationProperty" in node["rdf_type"]
            ):
                ns = "Property"
                if self.import_config.property_naming_policy == "label":
                    title = node["name"]
                elif self.import_config.property_naming_policy == "prefixed_label":
                    prefix = None
                    for onto in self.import_config.ontologies:
                        if (
                            onto.iri in node["iri"]
                            or onto.prefix_name
                            + self.import_config.property_naming_prefix_delimiter
                            in node["iri"]
                        ):
                            prefix = onto.prefix_name
                            break

                    if prefix:
                        name = None
                        if "name" in node:
                            name = node["name"]
                        elif ":" in node["iri"]:
                            name = node["iri"].split(":")[-1]
                        if name:
                            title = f"{prefix}{self.import_config.property_naming_prefix_delimiter}{name}"
                        else:
                            raise ValueError(
                                f"Could not find name for property {node['iri']}"
                            )
                    else:
                        raise ValueError(
                            f"Could not find prefix for property {node['iri']}"
                        )
                if self.import_config.property_naming_policy == "uuid":
                    title = OSW.get_osw_id(node_uuid)
            elif "owl:NamedIndividual" in node["rdf_type"]:
                ns = "Item"
                title = OSW.get_osw_id(node_uuid)
        else:  # e. g. owl:Axiom
            return None

        return f"{ns}:{title}"

    def _map_iri_to_osw(self, iri):
        result = None
        if iri in self._iri_dict:
            node = self._iri_dict[iri]
            result = self._get_page_name(node)
        if not result:
            result = iri
        return result

    def _apply_osw_structure(self):
        ps = self.parser_settings
        for node in self._g["@graph"]:
            for key in ps.ensure_multilang:
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
            for key in ps.ensure_array:
                if key in node and not isinstance(node[key], list):
                    node[key] = [node[key]]
            for key in ps.remove_unnamed:
                if key in node:
                    if isinstance(node[key], list):
                        node[key] = [
                            value for value in node[key] if not value.startswith("_:")
                        ]
                    elif isinstance(node[key], str) and node[key].startswith("_:"):
                        del node[key]

            if "rdf_type" in node and any(
                x in node["rdf_type"]
                for x in [
                    "owl:Class",
                    "owl:ObjectProperty",
                    "owl:DatatypeProperty",
                    "owl:AnnotationProperty",
                    "owl:NamedIndividual",
                ]
            ):
                node["uuid"] = str(self._get_uuid_from_iri(node["iri"]))

                # name = ""
                if "prefLabel" in node:
                    # if isinstance(node["prefLabel"], str): node["prefLabel"] = {"text": node["prefLabel"], "lang": "en"}
                    # if isinstance(node["prefLabel"], list): node["name"] = node["prefLabel"][0]["text"]
                    # else: node["name"] = node["prefLabel"]["text"]
                    node["name"] = node["prefLabel"][0]["text"]
                elif "label" in node:
                    node["name"] = node["label"][0]["text"]
                else:
                    print("No label: ", node["iri"])
                if "name" in node:
                    node["name"] = pascal_case(node["name"])

                # update iri dict
                self._iri_dict[node["iri"]] = node

                namespace = self._get_page_name(node).split(":")[0]
                title = self._get_page_name(node).replace(namespace + ":", "")
                node["meta"] = {
                    "wiki_page": {
                        "title": title,
                        "namespace": namespace,
                    }
                }

                for onto in self.import_config.ontologies:
                    if (
                        onto.prefix in node["iri"]
                        or onto.prefix_name + ":" in node["iri"]
                    ):
                        node["imported_from"] = (
                            onto.prefix_name
                            + ":"
                            + node["iri"]
                            .replace(onto.prefix, "")
                            .replace(onto.prefix_name + ":", "")
                        )
                        break

        self._map_iris(self._g["@graph"])

        # build an inverted property_dict
        self._prop_dict = {}
        for node in self._g["@graph"]:
            self._iri_dict[node["iri"]] = node
        for node in self._g["@graph"]:
            for key in node:
                if ":" in key and key not in self._prop_dict:
                    label = ""
                    if key in self._iri_dict and "label" in self._iri_dict[key]:
                        label = self._iri_dict[key]["label"][0]["text"]
                    self._prop_dict[key] = label
        # print the inverted property_dict
        for key, value in self._prop_dict.items():
            print(f'"{value}": "{key}"')

    def _map_iris(self, node_array):
        if not isinstance(node_array, list):
            node_array = [node_array]
        for node in node_array:
            if isinstance(node, dict):
                for key in node:
                    if key in self.parser_settings.map_uuid_iri:
                        if isinstance(node[key], list):
                            for i, val in enumerate(node[key]):
                                node[key][i] = self._map_iri_to_osw(node[key][i])
                        if isinstance(node[key], str):
                            node[key] = self._map_iri_to_osw(node[key])
                    if key == "restrictions":
                        print(key)
                    if isinstance(node[key], dict) or isinstance(node[key], list):
                        self._map_iris(node[key])

    def _create_entities(self):
        # create OSW entities
        limit = 3000  # choose a smaller number for tests
        counter = 0
        self._entities = []
        self._entities_json = []
        for index, node in enumerate(self._g["@graph"]):
            # restore class restrictions
            # if "_restrictions" in node:
            #    node["restrictions"] == node["_restrictions"]

            if counter < limit:
                if "rdf_type" in node and "label" in node:
                    e = None
                    if "owl:Class" in node["rdf_type"]:
                        e = self.import_config.base_class(**node)

                    if "owl:ObjectProperty" in node["rdf_type"]:
                        e = model.ObjectProperty(**node)

                    if "owl:DatatypeProperty" in node["rdf_type"]:
                        e = model.DataProperty(**node)

                    if "owl:AnnotationProperty" in node["rdf_type"]:
                        e = model.AnnotationProperty(**node)

                    if "owl:NamedIndividual" in node["rdf_type"]:
                        e = model.OwlIndividual(**node)

                    if e:
                        self._entities.append(e)
                        self._entities_json.append(
                            json.loads(e.json(exclude_none=True))
                        )
                        counter += 1

    class StoreOntologyParam(model.OswBaseModel):
        ontology: model.Ontology
        entities: List[model.OswBaseModel]

    def _store_ontology(self, param: StoreOntologyParam):
        import_page = self.osw.site.get_page(
            WtSite.GetPageParam(
                titles=["MediaWiki:Smw_import_" + param.ontology.prefix_name]
            )
        ).pages[0]
        text = (
            f"{param.ontology.prefix} | [{param.ontology.link} {param.ontology.name}]"
        )
        for e in param.entities:
            namespace = get_namespace(e)

            # see https://www.semantic-mediawiki.org/wiki/Help:Import_vocabulary
            if namespace == "Category":
                smw_import_type = "Category"
                if not hasattr(e, "subclass_of"):
                    e.subclass_of = []
                if len(e.subclass_of) == 0:
                    e.subclass_of = self.import_config.meta_class_title
            elif namespace == "Property":
                smw_import_type = "Type:" + e.cast(model.Property).property_type
            else:
                smw_import_type = "Item"
            iri = None
            if hasattr(e, "iri"):
                iri = e.iri
            if hasattr(e, "uri"):
                iri = e.uri
            if iri is not None:
                text += f"\n {iri.replace(param.ontology.prefix, '').replace(param.ontology.prefix_name + ':', '')}|{smw_import_type}"
            else:
                print("Error: Entity has not iri/uri property")

        import_page.set_slot_content("main", text)
        import_page.edit("import ontology")

        self.osw.store_entity(OSW.StoreEntityParam(entities=param.entities))

    @deprecated("use ontology.OntologyImporter.StoreOntologiesParam instead")
    class StoreOntologiesParam(model.OswBaseModel):
        entities: Optional[List[model.OswBaseModel]]
        """if we use model.Entity here, all instances are casted to model.Entity
        see: https://stackoverflow.com/questions/67366187/how-to-make-a-pydantic-field-accept-subclasses-using-type
        """
        # classes: Optional[List[model.Entity]]  # goes to NS Category
        # properties: Optional[List[model.Entity]]  # goes to NS Property
        # individuals: Optional[List[model.Entity]]  # goes to NS Item
        ontologies: Optional[List[model.Ontology]]
        dryrun: Optional[bool] = False

    def _store_ontologies(self, param: StoreOntologiesParam = None):
        entities = self._entities
        dry_run = self.import_config.dry_run
        ontologies = self.import_config.ontologies
        if param:
            entities = param.entities
            dry_run = param.dryrun
            ontologies = param.ontologies

        print(f"{len(entities)} classes to import")
        prefix_dict = {}
        for e in entities:
            if "//" in e.iri:
                if "http://purl.obolibrary.org/obo/" in e.iri:
                    # special handling for OBO ontologies
                    # ontologies are distinguished by the first part of the postfix
                    # e. g. http://purl.obolibrary.org/obo/BFO_0000050
                    postfix = e.iri.replace("http://purl.obolibrary.org/obo/", "")
                    key = (
                        "http://purl.obolibrary.org/obo/" + postfix.split("_")[0] + "_"
                    )
                elif "#" in e.iri:
                    key = e.iri.split("#")[0] + "#"
                else:
                    key = e.iri.replace(e.iri.split("/")[-1], "")
            else:
                key = e.iri.split(":")[0]  # e. g. "obo:OBO_0000050"
            if key not in prefix_dict:
                prefix_dict[key] = []
            prefix_dict[key].append(e)

        for prefix in prefix_dict.keys():
            onto = None
            for o in ontologies:
                if o.prefix == prefix or o.prefix_name == prefix:
                    onto = o
            if onto is None:
                print(f"Error: No ontology defined for prefix {prefix}")
            else:
                if not dry_run:
                    self._store_ontology(
                        OntologyImporter.StoreOntologyParam(
                            ontology=onto, entities=prefix_dict[prefix]
                        )
                    )
