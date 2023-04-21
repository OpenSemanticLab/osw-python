from __future__ import annotations

import importlib
import json
import os
import platform
import re
import sys
from enum import Enum
from typing import List, Optional, Union
from uuid import UUID

from jsonpath_ng.ext import parse
from pydantic import BaseModel, Field, create_model
from pydantic.main import ModelMetaclass

import osw.model.entity as model
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
        """Generates a OSW-ID based on the given uuid by prefixing "OSW" and removing all "-" from the uuid-string

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

    @model._basemodel_decorator
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
        """registers a new or updated schema in OSW by creating the corresponding category page

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

    @model._basemodel_decorator
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

    @model._basemodel_decorator
    class FetchSchemaParam(BaseModel):
        """_summary_

        Attributes
        ----------
        schema_title:
            the title (wiki page name) of the schema (default: Category:Item)
        root:
            marks the root iteration for a recursive fetch (internal param, default: True)
        mode:
            append or replace (default) current schema, see FetchSchemaMode
        """

        schema_title: Optional[str] = "Category:Item"
        root: Optional[bool] = True
        mode: Optional[
            str
        ] = "replace"  # type 'FetchSchemaMode' requires: 'from __future__ import annotations'

    def fetch_schema(self, fetchSchemaParam: FetchSchemaParam = None) -> None:
        """loads the given schema from the OSW instance and autogenerates python datasclasses within osw.model.entity from it

        Parameters
        ----------
        fetchSchemaParam, optional
            see FetchSchemaParam, by default None
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
                f"{exec_path}  --input {schema_path} --input-file-type jsonschema --output {temp_model_path} \
                --base-class OswBaseModel \
                --use-default \
                --enum-field-as-literal one \
                --use-title-as-name \
                --use-schema-description \
                --use-field-description \
                --encoding utf-8 \
                --use-double-quotes \
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

            # this is dirty, but required for autocompletion: https://stackoverflow.com/questions/62884543/pydantic-autocompletion-in-vs-code
            # idealy solved by custom templates in the future: https://github.com/koxudaxi/datamodel-code-generator/issues/860

            content = ""
            with open(temp_model_path, "r", encoding="utf-8") as f:
                content = f.read()
            os.remove(temp_model_path)

            content = re.sub(
                r"(import OswBaseModel)", "from pydantic import BaseModel", content, 1
            )  # remove import statement

            if fetchSchemaParam.mode == "replace":

                header = (
                    "from uuid import uuid4\n"
                    "from typing import TYPE_CHECKING, Type, TypeVar\n"
                    "from osw.model.static import OswBaseModel, Ontology\n"
                    "\n"
                    "if TYPE_CHECKING:\n"
                    "    from dataclasses import dataclass as _basemodel_decorator\n"
                    "else:\n"
                    "    _basemodel_decorator = lambda x: x  # noqa: E731\n"
                    "\n"
                )

                content = re.sub(
                    r"(class\s*\S*\s*\(\s*OswBaseModel\s*\)\s*:.*\n)",
                    header + r"\n\n\n\1",
                    content,
                    1,
                )  # replace first match
                content = re.sub(
                    r"(class\s*\S*\s*\(\s*OswBaseModel\s*\)\s*:.*\n)",
                    r"@_basemodel_decorator\n\1",
                    content,
                )
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
            Creates a instance of the class specified by the "type" attribute, default model.Entity
            Instance of model.Entity can be casted to any subclass with .cast(model.<class>)

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

    def store_entity(
        self, param: Union[StoreEntityParam, model.Entity, List[model.Entity]]
    ) -> None:
        """stores the given datasclass instance as OSW page by calling BaseModel.json()

        Parameters
        ----------
        entity
            StoreParam, the datasclass instance or a list of instances
        """

        namespace = None
        entity = param
        if isinstance(param, OSW.StoreEntityParam):
            entity = param.entities
            namespace = param.namespace

        if not isinstance(entity, list):
            entity = [entity]
        max_index = len(entity)
        for index, e in enumerate(entity):
            if namespace is None and isinstance(e, model.Item):
                namespace = "Item"
            if namespace is not None:
                entity_title = namespace + ":" + OSW.get_osw_id(e.uuid)
                page = self.site.get_WtPage(entity_title)
                jsondata = json.loads(
                    e.json(exclude_none=True)
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
            print(f"({index}/{max_index}) Entity stored at {page.get_url()}")

    def delete_entity(self, entity, comment: str = None):
        """deletes the given entity from the OSW instance

        Parameters
        ----------
        entity
            the dataclass instance to delete
        comment, optional
            command for the change log, by default None
        """
        if isinstance(entity, model.Item):
            entity_title = "Item:" + OSW.get_osw_id(entity.uuid)
            page = self.site.get_WtPage(entity_title)
        else:
            print("Error: Unsupported entity type")
            return
        if page.exists:
            page.delete(comment)
            print("Entity deleted: " + page.get_url())
        else:
            print(f"Entity '{entity_title}' does not exist!")

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
