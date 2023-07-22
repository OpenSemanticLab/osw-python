from __future__ import annotations

import importlib
import json
import os
import platform
import re
import sys
from enum import Enum
from typing import Any, List, Optional, Union
from uuid import UUID

from jsonpath_ng.ext import parse
from pydantic import BaseModel, Field, create_model
from pydantic.main import ModelMetaclass

import osw.model.entity as model
from osw.model.static import OswBaseModel
from osw.utils.util import parallelize
from osw.wiki_tools import SearchParam
from osw.wtsite import WtSite


class OswClassMetaclass(ModelMetaclass):
    def __new__(cls, name, bases, dic, osl_template, osl_footer_template):
        base_footer_cls = type(
            dic["__qualname__"] + "Footer",
            (BaseModel,),
            {
                "__annotations__": {"osl_template": str},
                "osl_template": Field(
                    default=osl_footer_template,
                    title=dic["__qualname__"] + "FooterTemplate",
                ),
            },
        )
        if "__annotations__" not in dic:
            dic["__annotations__"] = {}
        dic["__annotations__"]["osl_template"] = str
        dic["osl_template"] = Field(
            default=osl_template, title=dic["__qualname__"] + "Template"
        )
        dic["__annotations__"]["osl_footer"] = base_footer_cls
        dic["osl_footer"] = Field(
            default={"osl_template": osl_footer_template},
            title=dic["__qualname__"] + "Footer",
        )
        new_cls = super().__new__(cls, name, bases, dic)
        return new_cls


class OSW(BaseModel):
    """Bundles core functionalities of OpenSemanticWorld (OSW)"""

    uuid: str = "2ea5b605-c91f-4e5a-9559-3dff79fdd4a5"
    _protected_keywords = (
        "_osl_template",
        "_osl_footer",
    )  # private properties included in model export

    class Config:
        arbitrary_types_allowed = True  # neccessary to allow e.g. np.array as type

    site: WtSite

    @staticmethod
    def get_osw_id(uuid: uuid) -> str:
        """Generates a OSW-ID based on the given uuid by prefixing "OSW" and removing
        all '-' from the uuid-string

        Parameters
        ----------
        uuid
            uuid object, e. g. UUID("2ea5b605-c91f-4e5a-9559-3dff79fdd4a5")

        Returns
        -------
            OSW-ID string, e. g. OSW2ea5b605c91f4e5a95593dff79fdd4a5
        """
        return "OSW" + str(uuid).replace("-", "")

    @staticmethod
    def get_uuid(osw_id) -> uuid:
        """Returns the uuid for a given OSW-ID

        Parameters
        ----------
        osw_id
            OSW-ID string, e. g. OSW2ea5b605c91f4e5a95593dff79fdd4a5

        Returns
        -------
            uuid object, e. g. UUID("2ea5b605-c91f-4e5a-9559-3dff79fdd4a5")
        """
        return UUID(osw_id.replace("OSW", ""))

    class SchemaRegistration(BaseModel):
        """
        dataclass param of register_schema()

        Attributes
        ----------
        model_cls:
            the model class
        schema_name:
            the name of the schema
        schema_bases:
            list of base schemas (referenced by allOf)
        """

        class Config:
            arbitrary_types_allowed = True  # allow any class as type

        model_cls: ModelMetaclass
        schema_uuid = str  # Optional[str] = model_cls.__uuid__
        schema_name: str  # Optional[str] = model_cls.__name__
        schema_bases: List[str] = ["Category:Item"]

    def register_schema(self, schema_registration: SchemaRegistration):
        """Registers a new or updated schema in OSW by creating the corresponding
        category page.

        Parameters
        ----------
        schema_registration
            see SchemaRegistration
        """
        entity = schema_registration.model_cls

        jsondata = {}
        jsondata["uuid"] = schema_registration.schema_uuid
        jsondata["label"] = {"text": schema_registration.schema_name, "lang": "en"}
        jsondata["subclass_of"] = schema_registration.schema_bases

        if issubclass(entity, BaseModel):
            entity_title = "Category:" + OSW.get_osw_id(schema_registration.schema_uuid)
            page = self.site.get_WtPage(entity_title)

            page.set_slot_content("jsondata", jsondata)

            # entity = ModelMetaclass(entity.__name__, (BaseModel,), dict(entity.__dict__)) #strips base classes but fiels are already importet
            schema = json.loads(
                entity.schema_json(indent=4).replace("$ref", "dollarref")
            )

            jsonpath_expr = parse("$..allOf")
            # replace local definitions (#/definitions/...) with embedded definitions to prevent resolve errors in json-editor
            for match in jsonpath_expr.find(schema):
                result_array = []
                for subschema in match.value:
                    # pprint(subschema)
                    value = subschema["dollarref"]
                    if value.startswith("#"):
                        definition_jsonpath_expr = parse(
                            value.replace("#", "$").replace("/", ".")
                        )
                        for def_match in definition_jsonpath_expr.find(schema):
                            # pprint(def_match.value)
                            result_array.append(def_match.value)
                    else:
                        result_array.append(subschema)
                match.full_path.update_or_create(schema, result_array)
            if "definitions" in schema:
                del schema["definitions"]

            if "allOf" not in schema:
                schema["allOf"] = []
            for base in schema_registration.schema_bases:
                schema["allOf"].append(
                    {"$ref": f"/wiki/{base}?action=raw&slot=jsonschema"}
                )

            page.set_slot_content("jsonschema", schema)
        else:
            print("Error: Unsupported entity type")
            return

        page.edit()
        print("Entity stored at " + page.get_url())

    class SchemaUnregistration(BaseModel):
        """
        dataclass param of register_schema()

        Attributes
        ----------
        model_cls:
            the model class
        schema_name:
            the name of the schema
        schema_bases:
            list of base schemas (referenced by allOf)
        """

        class Config:
            arbitrary_types_allowed = True  # allow any class as type

        model_cls: Optional[ModelMetaclass]
        model_uuid: Optional[str]
        comment: Optional[str]

    def unregister_schema(self, schema_unregistration: SchemaUnregistration):
        """deletes the corresponding category page

        Parameters
        ----------
        schema_unregistration
            see SchemaUnregistration
        """
        uuid = ""
        if schema_unregistration.model_uuid:
            uuid = schema_unregistration.model_uuid
        elif (
            not uuid
            and schema_unregistration.model_cls
            and issubclass(schema_unregistration.model_cls, BaseModel)
        ):
            uuid = schema_unregistration.model_cls.__uuid__
        else:
            print("Error: Neither model nor model id provided")

        entity_title = "Category:" + OSW.get_osw_id(uuid)
        page = self.site.get_WtPage(entity_title)
        page.delete(schema_unregistration.comment)

    class FetchSchemaMode(Enum):
        """Modes of the FetchSchemaParam class

        Attributes
        ----------
        append:
            append to the current model
        replace:
            replace the current model
        """

        append = "append"  # append to the current model
        replace = "replace"  # replace the current model

    class FetchSchemaParam(BaseModel):
        """_summary_

        Attributes
        ----------
        schema_title:
            the title (wiki page name) of the schema (default: Category:Item)
        root:
            marks the root iteration for a recursive fetch (internal param,
            default: True)
        mode:
            append or replace (default) current schema, see FetchSchemaMode
        """

        schema_title: Optional[str] = "Category:Item"
        root: Optional[bool] = True
        mode: Optional[
            str
        ] = "replace"  # type 'FetchSchemaMode' requires: 'from __future__ import annotations'

    def fetch_schema(self, fetchSchemaParam: FetchSchemaParam = None) -> None:
        """Loads the given schema from the OSW instance and autogenerates python
        datasclasses within osw.model.entity from it

        Parameters
        ----------
        fetchSchemaParam
            See FetchSchemaParam, by default None
        """
        site_cache_state = self.site.get_cache_enabled()
        self.site.enable_cache()
        if fetchSchemaParam is None:
            fetchSchemaParam = OSW.FetchSchemaParam()
        schema_title = fetchSchemaParam.schema_title
        root = fetchSchemaParam.root
        schema_name = schema_title.split(":")[-1]
        page = self.site.get_WtPage(schema_title)
        if schema_title.startswith("Category:"):
            schema_str = json.dumps(page.get_slot_content("jsonschema"))
        else:
            schema_str = page.get_content()
        schema = json.loads(
            schema_str.replace("$ref", "dollarref")
        )  # '$' is a special char for root object in jsonpath
        print(f"Fetch {schema_title}")

        jsonpath_expr = parse("$..dollarref")
        for match in jsonpath_expr.find(schema):
            # value = "https://" + self.site._site.host + match.value
            if match.value.startswith("#"):
                continue  # skip self references
            ref_schema_title = match.value.replace("/wiki/", "").split("?")[0]
            ref_schema_name = ref_schema_title.split(":")[-1] + ".json"
            value = ""
            for i in range(0, schema_name.count("/")):
                value += "../"  # created relative path to top-level schema dir
            value += ref_schema_name  # create a reference to a local file
            match.full_path.update_or_create(schema, value)
            # print(f"replace {match.value} with {value}")
            if (
                ref_schema_title != schema_title
            ):  # prevent recursion in case of self references
                self.fetch_schema(
                    OSW.FetchSchemaParam(schema_title=ref_schema_title, root=False)
                )  # resolve references recursive

        model_dir_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "model"
        )  # src/model
        schema_path = os.path.join(model_dir_path, schema_name + ".json")
        os.makedirs(os.path.dirname(schema_path), exist_ok=True)
        with open(schema_path, "w", encoding="utf-8") as f:
            schema_str = json.dumps(schema, ensure_ascii=False, indent=4).replace(
                "dollarref", "$ref"
            )
            # print(schema_str)
            f.write(schema_str)

        # result_model_path = schema_path.replace(".json", ".py")
        result_model_path = os.path.join(model_dir_path, "entity.py")
        temp_model_path = os.path.join(model_dir_path, "temp.py")
        if root:
            exec_name = "datamodel-codegen"
            if platform.system() == "Windows":
                exec_name += ".exe"
            exec_path = os.path.join(
                os.path.dirname(os.path.abspath(sys.executable)), exec_name
            )
            if not os.path.isfile(exec_path):
                exec_path = os.path.join(
                    os.path.dirname(os.path.abspath(sys.executable)),
                    "Scripts",
                    exec_name,
                )
            if not os.path.isfile(exec_path):
                print("Error: datamodel-codegen not found")
                return
            os.system(
                f"{exec_path}  \
                --input {schema_path} \
                --input-file-type jsonschema \
                --output {temp_model_path} \
                --base-class osw.model.static.OswBaseModel \
                --use-default \
                --enum-field-as-literal one \
                --use-title-as-name \
                --use-schema-description \
                --use-field-description \
                --encoding utf-8 \
                --use-double-quotes \
                --collapse-root-models \
                --reuse-model \
            "
            )
            # see https://koxudaxi.github.io/datamodel-code-generator/
            # --base-class OswBaseModel: use a custom base class
            # --custom-template-dir src/model/template_data/
            # --extra-template-data src/model/template_data/extra.json
            # --use-default: Use default value even if a field is required
            # --enum-field-as-literal one: for static properties like osl_template
            # --use-schema-description: Use schema description to populate class docstring
            # --use-field-description: Use schema description to populate field docstring
            # --use-title-as-name: use titles as class names of models, e. g. for the footer templates
            # --collapse-root-models: Models generated with a root-type field will be merged
            # into the models using that root-type model, e. g. for Entity.statements
            # --reuse-model: Re-use models on the field when a module has the model with the same content

            # this is dirty, but required for autocompletion: https://stackoverflow.com/questions/62884543/pydantic-autocompletion-in-vs-code
            # idealy solved by custom templates in the future: https://github.com/koxudaxi/datamodel-code-generator/issues/860

            content = ""
            with open(temp_model_path, "r", encoding="utf-8") as f:
                content = f.read()
            os.remove(temp_model_path)

            # Statement and its subclasses are a complex case that needs manual fixing

            # datamodel-codegen <= 0.15.0
            # make statement classes subclasses of Statement
            content = re.sub(
                r"ObjectStatement\(OswBaseModel\)",
                r"ObjectStatement(Statement)",
                content,
            )
            content = re.sub(
                r"DataStatement\(OswBaseModel\)", r"DataStatement(Statement)", content
            )
            content = re.sub(
                r"QuantityStatement\(OswBaseModel\)",
                r"QuantityStatement(Statement)",
                content,
            )
            # make statement lists union of all statement types
            content = re.sub(
                r"List\[Statement\]",
                r"List[Union[ObjectStatement, DataStatement, QuantityStatement]]",
                content,
            )
            # remove Statement class
            content = re.sub(
                r"(class\s*"
                + "Statement"
                + r"\s*\(\s*\S*\s*\)\s*:.*\n[\s\S]*?(?:[^\S\n]*\n){3,})",
                "",
                content,
                count=1,
            )
            # rename Statement1 to Statement
            content = re.sub(r"Statement1", r"Statement", content)
            # add forward refs
            content = re.sub(
                r"Statement.update_forward_refs\(\)",
                r"Statement.update_forward_refs()\nObjectStatement.update_forward_refs()\nDataStatement.update_forward_refs()\nQuantityStatement.update_forward_refs()",
                content,
            )
            pattern = re.compile(
                r"(class\s*"
                + "Statement"
                + r"\s*\(\s*\S*\s*\)\s*:.*\n[\s\S]*?(?:[^\S\n]*\n){3,})"
            )  # match Statement class definition
            for cls in re.findall(pattern, content):
                # remove class
                content = re.sub(
                    r"(class\s*"
                    + "Statement"
                    + r"\s*\(\s*\S*\s*\)\s*:.*\n[\s\S]*?(?:[^\S\n]*\n){3,})",
                    "",
                    content,
                    count=1,
                )
                content = re.sub(
                    r"(class\s*\S*\s*\(\s*Statement\s*\)\s*:.*\n)",
                    cls + r"\1",
                    content,
                    1,
                )  # insert class definition before first reference
                break

            # datamodel-codegen > 0.15.0
            # Rename statement classes (ObjectStatement, DataStatement, QuantityStatement)
            # content = re.sub(r"ObjectStatement", r"_ObjectStatement", content)
            # content = re.sub(r"DataStatement", r"_DataStatement", content)
            # content = re.sub(r"QuantityStatement", r"_QuantityStatement", content)
            # class Statement1(_ObjectStatement):
            # content = re.sub(r"class\s*\S*(\s*\(\s*_ObjectStatement\s*\))", r"class ObjectStatement\1", content)
            # content = re.sub(r"class\s*\S*(\s*\(\s*_DataStatement\s*\))", r"class DataStatement\1", content)
            # content = re.sub(r"class\s*\S*(\s*\(\s*_QuantityStatement\s*\))", r"class QuantityStatement\1", content)
            # Union[Statement1, Statement2, Statement3] and Statement<x>.update_forward_refs()
            # content = re.sub(r"Statement1", r"ObjectStatement", content)
            # content = re.sub(r"Statement2", r"DataStatement", content)
            # content = re.sub(r"Statement3", r"QuantityStatement", content)

            if fetchSchemaParam.mode == "replace":

                header = (
                    "from uuid import uuid4\n"
                    "from typing import Type, TypeVar\n"
                    "from osw.model.static import OswBaseModel, Ontology\n"
                    "\n"
                )

                content = re.sub(
                    r"(class\s*\S*\s*\(\s*OswBaseModel\s*\)\s*:.*\n)",
                    header + r"\n\n\n\1",
                    content,
                    1,
                )  # add header before first class declaration

                content = re.sub(
                    r"(UUID = Field\(...)",
                    r"UUID = Field(default_factory=uuid4",
                    content,
                )  # enable default value for uuid
                with open(result_model_path, "w", encoding="utf-8") as f:
                    f.write(content)

            if fetchSchemaParam.mode == "append":
                org_content = ""
                with open(result_model_path, "r", encoding="utf-8") as f:
                    org_content = f.read()

                pattern = re.compile(
                    r"class\s*([\S]*)\s*\(\s*\S*\s*\)\s*:.*\n"
                )  # match class definition [\s\S]*(?:[^\S\n]*\n){2,}
                for cls in re.findall(pattern, org_content):
                    print(cls)
                    content = re.sub(
                        r"(class\s*"
                        + cls
                        + r"\s*\(\s*\S*\s*\)\s*:.*\n[\s\S]*?(?:[^\S\n]*\n){3,})",
                        "",
                        content,
                        count=1,
                    )  # replace duplicated classes

                content = re.sub(
                    r"(from __future__ import annotations)", "", content, 1
                )  # remove import statement
                # print(content)
                with open(result_model_path, "a", encoding="utf-8") as f:
                    f.write(content)

            importlib.reload(model)  # reload the updated module
            if not site_cache_state:
                self.site.disable_cache()  # restore original state

    def load_entity(self, entity_title) -> model.Entity:
        """Loads the entity with the given wiki page name from the OSW instance.
        Creates an instance of the class specified by the "type" attribute, default
        model.Entity. An instance of model.Entity can be cast to any subclass with
        .cast(model.<class>) .

        Parameters
        ----------
        entity_title
            the wiki page name

        Returns
        -------
            the dataclass instance
        """
        entity = None
        schemas = []
        page = self.site.get_WtPage(entity_title)
        jsondata = page.get_slot_content("jsondata")
        if jsondata:
            for category in jsondata["type"]:
                schema = self.site.get_WtPage(category).get_slot_content("jsonschema")
                schemas.append(schema)

        if len(schemas) == 0:
            print("Error: no schema defined")

        elif len(schemas) == 1:
            cls = schemas[0]["title"]
            entity = eval(f"model.{cls}(**jsondata)")

        else:
            bases = []
            for schema in schemas:
                bases.append(eval("model." + schema["title"]))
            cls = create_model("Test", __base__=tuple(bases))
            entity = cls(**jsondata)

        return entity

    class StoreEntityParam(model.OswBaseModel):
        entities: Union[model.Entity, List[model.Entity]]
        namespace: Optional[str]
        parallel: Optional[bool] = False
        debug: Optional[bool] = False

    def store_entity(
        self, param: Union[StoreEntityParam, model.Entity, List[model.Entity]]
    ) -> None:
        """stores the given dataclass instance as OSW page by calling BaseModel.json()

        Parameters
        ----------
        param:
            StoreEntityParam, the dataclass instance or a list of instances
        """
        if isinstance(param, model.Entity):
            param = OSW.StoreEntityParam(entities=[param])
        if isinstance(param, list):
            param = OSW.StoreEntityParam(entities=param)
        if not isinstance(param.entities, list):
            param.entities = [param.entities]

        max_index = len(param.entities)
        if max_index >= 5:
            param.parallel = True

        def store_entity_(
            entity: model.Entity, index: int = None, namespace_=param.namespace
        ) -> None:
            if namespace_ is None and isinstance(entity, model.Item):
                namespace_ = "Item"
            if namespace_ is not None:
                entity_title = namespace_ + ":" + OSW.get_osw_id(entity.uuid)
                page = self.site.get_WtPage(entity_title)
                jsondata = json.loads(
                    entity.json(exclude_none=True)
                )  # use pydantic serialization, skip none values
                page.set_slot_content("jsondata", jsondata)
            else:
                print("Error: Unsupported entity type")
                return
            page.set_slot_content(
                "header", "{{#invoke:Entity|header}}"
            )  # required for json parsing and header rendering
            page.set_slot_content(
                "footer", "{{#invoke:Entity|footer}}"
            )  # required for footer rendering
            page.edit()
            if index is None:
                print(f"Entity stored at {page.get_url()}.")
            else:
                print(
                    f"({index + 1}/{max_index}) Entity stored at " f"{page.get_url()}."
                )

        if param.parallel:
            _ = parallelize(store_entity_, param.entities, flush_at_end=param.debug)
        else:
            _ = [store_entity_(e, i) for i, e in enumerate(param.entities)]

    class DeleteEntityParam(model.OswBaseModel):
        entities: List[model.Entity]
        comment: Optional[str] = None
        parallel: Optional[bool] = False
        debug: Optional[bool] = False

    def delete_entity(self, entity: Union[Any, DeleteEntityParam], comment: str = None):

        """Deletes the given entity/entities from the OSW instance."""
        if not isinstance(entity, OSW.DeleteEntityParam):
            if isinstance(entity, list):
                entity = OSW.DeleteEntityParam(entities=entity)
            else:
                entity = OSW.DeleteEntityParam(entities=[entity])
        if comment is not None:
            entity.comment = comment
        if len(entity.entities) >= 5:
            entity.parallel = True

        def delete_entity_(entity_, comment_: str = None):
            """Deletes the given entity from the OSW instance.

            Parameters
            ----------
            entity_:
                The dataclass instance to delete
            comment_:
                Command for the change log, by default None
            """
            if isinstance(entity_, model.Item):
                entity_title = "Item:" + OSW.get_osw_id(entity_.uuid)
                page = self.site.get_WtPage(entity_title)
            else:
                print("Error: Unsupported entity type")
                return
            if page.exists:
                page.delete(comment_)
                print("Entity deleted: " + page.get_url())
            else:
                print(f"Entity '{entity_title}' does not exist!")

        if entity.parallel:
            _ = parallelize(
                delete_entity_,
                entity.entities,
                flush_at_end=entity.debug,
                comment_=entity.comment,
            )
        else:
            _ = [delete_entity_(e, entity.comment) for e in entity.entities]

    class QueryInstancesParam(model.OswBaseModel):
        categories: List[Union[str, OswBaseModel]]
        parallel: Optional[bool] = False
        debug: Optional[bool] = False
        limit: Optional[int] = 1000

    def query_instances(
        self, category: Union[str, OswBaseModel, OSW.QueryInstancesParam]
    ) -> List[str]:
        def get_page_title(category_: Union[str, OswBaseModel]) -> str:
            error_msg = (
                "Category must be a string, a dataclass instance with "
                "a 'type' attribute or osw.wiki_tools.SearchParam."
            )
            if isinstance(category_, str):
                return category_.split(":")[-1]  # page title w/o namespace
            elif isinstance(category_, model.OswBaseModel):
                type_ = getattr(category_, "type", None)
                if type_:
                    full_page_title = type_[0]
                    return full_page_title.split(":")[-1]  # page title w/o namespace
                else:
                    raise TypeError(error_msg)
            else:
                raise TypeError(error_msg)

        if isinstance(category, OSW.QueryInstancesParam):
            page_titles = [get_page_title(cat) for cat in category.categories]
        else:
            page_titles = [get_page_title(category)]
            category = OSW.QueryInstancesParam(category=page_titles)

        search_param = SearchParam(
            query=[f"[[HasType::Category:{page_title}]]" for page_title in page_titles],
            **category.dict(exclude={"categories"}),
        )
        full_page_titles = self.site.semantic_search(search_param)
        return full_page_titles

    class _ImportOntologyParam(model.OswBaseModel):
        ontology: model.Ontology
        entities: List[model.Entity]
        properties: Optional[List[model.Entity]]

    def _import_ontology(self, param: _ImportOntologyParam):
        import_page = self.site.get_WtPage(
            "MediaWiki:Smw_import_" + param.ontology.prefix_name
        )
        text = f"{param.ontology.prefix}|[{param.ontology.link} {param.ontology.name}]"
        for e in param.entities:
            iri = None
            if hasattr(e, "iri"):
                iri = e.iri
            if hasattr(e, "uri"):
                iri = e.uri
            if iri is not None:
                text += f"\n {iri.replace(param.ontology.prefix, '')}|Category"
            else:
                print("Error: Entity has not iri/uri property")
        import_page.set_slot_content("main", text)
        import_page.edit("import ontology")

        self.store_entity(
            OSW.StoreEntityParam(namespace="Category", entities=param.entities)
        )

    class ImportOntologyParam(model.OswBaseModel):
        entities: List[model.Entity]
        ontologies: List[model.Ontology]

    def import_ontology(self, param: ImportOntologyParam):
        prefix_dict = {}
        for e in param.entities:
            if "#" in e.uri:
                key = e.uri.split("#")[0] + "#"
            else:
                key = e.uri.replace(e.uri.split("/")[-1], "")
            if key not in prefix_dict:
                prefix_dict[key] = []
            prefix_dict[key].append(e)

        for prefix in prefix_dict.keys():
            onto = None
            for o in param.ontologies:
                if o.prefix == prefix:
                    onto = o
            if onto is None:
                print(f"Error: No ontology defined for prefix {prefix}")
            else:
                self._import_ontology(
                    OSW._ImportOntologyParam(
                        ontology=onto, entities=prefix_dict[prefix]
                    )
                )
