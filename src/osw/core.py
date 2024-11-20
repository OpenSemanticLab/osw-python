from __future__ import annotations

import importlib
import json
import os
import platform
import re
import sys
from copy import deepcopy
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union
from uuid import UUID
from warnings import warn

import rdflib
from jsonpath_ng.ext import parse
from pydantic.v1 import BaseModel, PrivateAttr, create_model, validator
from pyld import jsonld

import osw.model.entity as model
from osw.model.static import OswBaseModel
from osw.utils.templates import (
    compile_handlebars_template,
    eval_compiled_handlebars_template,
)
from osw.utils.util import parallelize
from osw.utils.wiki import (
    get_full_title,
    get_namespace,
    get_title,
    get_uuid,
    is_empty,
    namespace_from_full_title,
    title_from_full_title,
)
from osw.wiki_tools import SearchParam
from osw.wtsite import WtPage, WtSite


# Reusable type definitions
class OverwriteOptions(Enum):
    """Options for overwriting properties"""

    true = True
    """Always overwrite a property"""
    false = False
    """Never overwrite a property"""
    only_empty = "only empty"
    """Only overwrite if the property is empty"""
    # todo: implement "merge",
    # todo: implement "append",
    #   Don't replace the properties but for properties of type array or dict, append
    #   the values of the local entity to the remote entity, make sure  # to not
    #   append duplicates
    # todo: implement "only older",
    # todo: implement read out from the version history of the page


class AddOverwriteClassOptions(Enum):
    replace_remote = "replace remote"
    """Replace the entity with the new one, removes all properties that are not
    present in the local entity"""
    keep_existing = "keep existing"
    """Keep the entity, does not add or remove any properties, if the page exists, the
    entity is not stored"""
    none = None
    """Not an option to choose from, will be replaced by the default remote properties
    """


OVERWRITE_CLASS_OPTIONS = Union[OverwriteOptions, AddOverwriteClassOptions]


class OSW(BaseModel):
    """Bundles core functionalities of OpenSemanticWorld (OSW)"""

    uuid: str = "2ea5b605-c91f-4e5a-9559-3dff79fdd4a5"
    _protected_keywords = (
        "_osl_template",
        "_osl_footer",
    )  # private properties included in model export

    class Config:
        arbitrary_types_allowed = True  # necessary to allow e.g. np.array as type

    site: WtSite

    @staticmethod
    def get_osw_id(uuid: uuid) -> str:
        """Generates a OSW-ID based on the given uuid by prefixing "OSW" and removing
        all '-' from the uuid-string

        Parameters
        ----------
        uuid
            uuid object, e.g. UUID("2ea5b605-c91f-4e5a-9559-3dff79fdd4a5")

        Returns
        -------
            OSW-ID string, e.g. OSW2ea5b605c91f4e5a95593dff79fdd4a5
        """
        return "OSW" + str(uuid).replace("-", "")

    @staticmethod
    def get_uuid(osw_id) -> uuid:
        """Returns the uuid for a given OSW-ID

        Parameters
        ----------
        osw_id
            OSW-ID string, e.g. OSW2ea5b605c91f4e5a95593dff79fdd4a5

        Returns
        -------
            uuid object, e.g. UUID("2ea5b605-c91f-4e5a-9559-3dff79fdd4a5")
        """
        return UUID(osw_id.replace("OSW", ""))

    class SortEntitiesResult(OswBaseModel):
        by_name: Dict[str, List[OswBaseModel]]
        by_type: Dict[str, List[OswBaseModel]]

    @staticmethod
    def sort_list_of_entities_by_class(
        entities: List[OswBaseModel],
        exclude_typeless: bool = True,
        raise_error: bool = False,
    ) -> SortEntitiesResult:
        """Sorts a list of entities by class name and type.

        Parameters
        ----------
        entities:
            List of entities to be sorted
        exclude_typeless:
            Exclude entities, which are instances of a class that does not
            define a field 'type'
        raise_error:
            Raise an error if an entity can not be processed because it is an
            instance of class that does not define a field 'type'
        """
        by_name = {}
        by_type = {}
        for entity in entities:
            # Get class name
            name = entity.__class__.__name__
            # See if the class has a type field
            if "type" not in entity.__class__.__fields__:
                if raise_error:
                    raise AttributeError(
                        f"Instance '{entity}' of class '{name}' can not be processed "
                        f"as the class does not define a field 'type'."
                    )
                if exclude_typeless:
                    warn(
                        f"Skipping instance '{entity}' of class '{name}' as the class "
                        f"does not define a field 'type'."
                    )
                    # Excludes the respective entity from the list which will be
                    #  processed further:
                    continue
                model_type = None
            else:
                # Get class type if available
                model_type = entity.__class__.__fields__["type"].default[0]
            # Add entity to by_name
            if name not in by_name:
                by_name[name] = []
            by_name[name].append(entity)
            # Add entity to by_type
            if model_type not in by_type:
                by_type[model_type] = []
            by_type[model_type].append(entity)

        return OSW.SortEntitiesResult(by_name=by_name, by_type=by_type)

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

        model_cls: Type[OswBaseModel]
        schema_uuid: str  # Optional[str] = model_cls.__uuid__
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

            page = WtPage(wtSite=self.site, title=entity_title)
            if page.exists:
                page = self.site.get_page(
                    WtSite.GetPageParam(titles=[entity_title])
                ).pages[0]

            page.set_slot_content("jsondata", jsondata)

            schema = json.loads(
                entity.schema_json(indent=4).replace("$ref", "dollarref")
            )

            jsonpath_expr = parse("$..allOf")
            # Replace local definitions (#/definitions/...) with embedded definitions
            #  to prevent resolve errors in json-editor
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

        model_cls: Optional[Type[OswBaseModel]]
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
        page = self.site.get_page(WtSite.GetPageParam(titles=[entity_title])).pages[0]
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
        """Param for fetch_schema()

        Attributes
        ----------
        schema_title:
            one or multiple titles (wiki page name) of schemas (default: Category:Item)
        mode:
            append or replace (default) current schema, see FetchSchemaMode
        """

        schema_title: Optional[Union[List[str], str]] = "Category:Item"
        mode: Optional[str] = (
            "replace"
            # type 'FetchSchemaMode' requires: 'from __future__ import annotations'
        )

    def fetch_schema(self, fetchSchemaParam: FetchSchemaParam = None) -> None:
        """Loads the given schemas from the OSW instance and autogenerates python
        datasclasses within osw.model.entity from it

        Parameters
        ----------
        fetchSchemaParam
            See FetchSchemaParam, by default None
        """
        if not isinstance(fetchSchemaParam.schema_title, list):
            fetchSchemaParam.schema_title = [fetchSchemaParam.schema_title]
        first = True
        for schema_title in fetchSchemaParam.schema_title:
            mode = fetchSchemaParam.mode
            if not first:  # 'replace' makes only sense for the first schema
                mode = "append"
            self._fetch_schema(
                OSW._FetchSchemaParam(schema_title=schema_title, mode=mode)
            )
            first = False

    class _FetchSchemaParam(BaseModel):
        """Internal param for _fetch_schema()

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
        mode: Optional[str] = (
            "replace"
            # type 'FetchSchemaMode' requires: 'from __future__ import annotations'
        )

    def _fetch_schema(self, fetchSchemaParam: _FetchSchemaParam = None) -> None:
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
            fetchSchemaParam = OSW._FetchSchemaParam()
        schema_title = fetchSchemaParam.schema_title
        root = fetchSchemaParam.root
        schema_name = schema_title.split(":")[-1]
        page = self.site.get_page(WtSite.GetPageParam(titles=[schema_title])).pages[0]
        if not page.exists:
            print(f"Error: Page {schema_title} does not exist")
            return
        # not only in the JsonSchema namespace the schema is located in the main sot
        # in all other namespaces, the json_schema slot is used
        if schema_title.startswith("JsonSchema:"):
            schema_str = ""
            if page.get_slot_content("main"):
                schema_str = json.dumps(page.get_slot_content("main"))
        else:
            schema_str = ""
            if page.get_slot_content("jsonschema"):
                schema_str = json.dumps(page.get_slot_content("jsonschema"))
        if (schema_str is None) or (schema_str == ""):
            print(f"Error: Schema {schema_title} does not exist")
            schema_str = "{}"  # empty schema to make reference work
        schema = json.loads(
            schema_str.replace("$ref", "dollarref").replace(
                # '$' is a special char for root object in jsonpath
                '"allOf": [',
                '"allOf": [{},',
            )
            # fix https://github.com/koxudaxi/datamodel-code-generator/issues/1910
        )
        print(f"Fetch {schema_title}")

        jsonpath_expr = parse("$..dollarref")
        for match in jsonpath_expr.find(schema):
            # value = "https://" + self.site._site.host + match.value
            if match.value.startswith("#"):
                continue  # skip self references
            ref_schema_title = match.value.replace("/wiki/", "").split("?")[0]
            ref_schema_name = ref_schema_title.split(":")[-1] + ".json"
            value = ""
            for _i in range(0, schema_name.count("/")):
                value += "../"  # created relative path to top-level schema dir
            value += ref_schema_name  # create a reference to a local file
            # keep document-relative jsonpointer if present
            if "#/" in match.value:
                value += "#/" + match.value.split("#/")[-1]
            match.full_path.update_or_create(schema, value)
            # print(f"replace {match.value} with {value}")
            if (
                ref_schema_title != schema_title
            ):  # prevent recursion in case of self references
                self._fetch_schema(
                    OSW._FetchSchemaParam(schema_title=ref_schema_title, root=False)
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
            # default: assume datamodel-codegen is in PATH
            exec_path = exec_name
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
                --use-unique-items-as-set \
                --enum-field-as-literal all \
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
            # --use-unique-items-as-set: define field type as `set` when the field
            #  attribute has`uniqueItems`
            # --enum-field-as-literal all: prevent 'value is not a valid enumeration
            #  member' errors after schema reloading
            # --use-schema-description: Use schema description to populate class
            #  docstring
            # --use-field-description: Use schema description to populate field
            #  docstring
            # --use-title-as-name: use titles as class names of models, e.g. for the
            #  footer templates
            # --collapse-root-models: Models generated with a root-type field will be
            #  merged
            # into the models using that root-type model, e.g. for Entity.statements
            # --reuse-model: Re-use models on the field when a module has the model
            #  with the same content

            content = ""
            with open(temp_model_path, "r", encoding="utf-8") as f:
                content = f.read()
            os.remove(temp_model_path)

            content = re.sub(
                r"(UUID = Field\(...)",
                r"UUID = Field(default_factory=uuid4",
                content,
            )  # enable default value for uuid

            # we are now using pydantic.v1
            # pydantic imports lead to uninitialized fields (FieldInfo still present)
            content = re.sub(
                r"(from pydantic import)", "from pydantic.v1 import", content
            )

            # remove field param unique_items
            # --use-unique-items-as-set still keeps unique_items=True as Field param
            # which was removed, see https://github.com/pydantic/pydantic-core/issues/296
            # --output-model-type pydantic_v2.BaseModel fixes that but generated models
            # are not v1 compatible mainly by using update_model()
            content = re.sub(r"(,?\s*unique_items=True\s*)", "", content)

            if fetchSchemaParam.mode == "replace":
                header = (
                    "from uuid import uuid4\n"
                    "from typing import Type, TypeVar\n"
                    "from osw.model.static import OswBaseModel, Ontology\n"
                    # "from osw.model.static import *\n"
                    "\n"
                )

                content = re.sub(
                    pattern=r"(class\s*\S*\s*\(\s*OswBaseModel\s*\)\s*:.*\n)",
                    repl=header + r"\n\n\n\1",
                    string=content,
                    count=1,
                )  # add header before first class declaration

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
                    pattern=r"(from __future__ import annotations)",
                    repl="",
                    string=content,
                    count=1,
                )  # remove import statement
                # print(content)
                with open(result_model_path, "a", encoding="utf-8") as f:
                    f.write(content)

            importlib.reload(model)  # reload the updated module
            if not site_cache_state:
                self.site.disable_cache()  # restore original state

    class LoadEntityParam(BaseModel):
        """Param for load_entity()"""

        titles: Union[str, List[str]]
        """The pages titles to load - one or multiple titles (wiki page name) of
        entities"""
        autofetch_schema: Optional[bool] = True
        """If true, load the corresponding schemas /
        categories ad-hoc if not already present"""
        disable_cache: bool = False
        """If true, disable the cache for the loading process"""

        def __init__(self, **data):
            super().__init__(**data)
            if not isinstance(self.titles, list):
                self.titles = [self.titles]

    class LoadEntityResult(BaseModel):
        """Result of load_entity()"""

        entities: Union[model.Entity, List[model.Entity]]
        """The dataclass instance(s)"""

    def load_entity(
        self, entity_title: Union[str, List[str], LoadEntityParam]
    ) -> Union[model.Entity, List[model.Entity], LoadEntityResult]:
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
            the dataclass instance if only a single title is given
            a list of dataclass instances if a list of titles is given
            a LoadEntityResult instance if a LoadEntityParam is given
        """
        if isinstance(entity_title, str):
            param = OSW.LoadEntityParam(titles=[entity_title])
        elif isinstance(entity_title, list):
            param = OSW.LoadEntityParam(titles=entity_title)
        else:
            param = entity_title

        # store original cache state
        cache_state = self.site.get_cache_enabled()
        if param.disable_cache:
            self.site.disable_cache()
        if not cache_state and param.disable_cache:
            # enable cache to speed up loading
            self.site.enable_cache()

        entities = []
        pages = self.site.get_page(WtSite.GetPageParam(titles=param.titles)).pages
        for page in pages:
            entity = None
            schemas = []
            schemas_fetched = True
            jsondata = page.get_slot_content("jsondata")
            if jsondata:
                for category in jsondata["type"]:
                    schema = (
                        self.site.get_page(WtSite.GetPageParam(titles=[category]))
                        .pages[0]
                        .get_slot_content("jsonschema")
                    )
                    schemas.append(schema)
                    # generate model if not already exists
                    cls = schema["title"]
                    if not hasattr(model, cls):
                        if param.autofetch_schema:
                            self.fetch_schema(
                                OSW.FetchSchemaParam(
                                    schema_title=category, mode="append"
                                )
                            )
                    if not hasattr(model, cls):
                        schemas_fetched = False
                        print(
                            f"Error: Model {cls} not found. Schema {category} needs to "
                            f"be fetched first."
                        )
            if not schemas_fetched:
                continue

            if len(schemas) == 0:
                print("Error: no schema defined")

            elif len(schemas) == 1:
                cls = getattr(model, schemas[0]["title"])
                entity: model.Entity = cls(**jsondata)

            else:
                bases = []
                for schema in schemas:
                    bases.append(getattr(model, schema["title"]))
                cls = create_model("Test", __base__=tuple(bases))
                entity: model.Entity = cls(**jsondata)

            if entity is not None:
                # make sure we do not override existing meta data
                if not hasattr(entity, "meta") or entity.meta is None:
                    entity.meta = model.Meta()
                if (
                    not hasattr(entity.meta, "wiki_page")
                    or entity.meta.wiki_page is None
                ):
                    entity.meta.wiki_page = model.WikiPage()
                entity.meta.wiki_page.namespace = namespace_from_full_title(page.title)
                entity.meta.wiki_page.title = title_from_full_title(page.title)

            entities.append(entity)
        # restore original cache state
        if cache_state:
            self.site.enable_cache()
        else:
            self.site.disable_cache()

        if isinstance(entity_title, str):  # single title
            if len(entities) >= 1:
                return entities[0]
            else:
                return None
        if isinstance(entity_title, list):  # list of titles
            return entities
        if isinstance(entity_title, OSW.LoadEntityParam):  # LoadEntityParam
            return OSW.LoadEntityResult(entities=entities)

    class OverwriteClassParam(OswBaseModel):
        model: Type[OswBaseModel]  # ModelMetaclass
        """The model class for which this is the overwrite params object."""
        overwrite: Optional[OVERWRITE_CLASS_OPTIONS] = False
        """Defines the overall overwriting behavior. Used for any property if the
        property specific setting is not set."""
        per_property: Optional[Dict[str, OverwriteOptions]] = None
        """A key (property name) - value (overwrite setting) pair. Careful! - When
        setting values of this dictionary after validation, the validator won't be
        called again. The same applies for the __init__ function!"""
        _per_property: Dict[str, OVERWRITE_CLASS_OPTIONS] = PrivateAttr()
        """Private property, for internal use only. Use 'per_property' instead"""

        @validator("per_property")
        def validate_per_property(cls, per_property, values):
            model_ = values.get("model")
            field_names = list(model_.__fields__.keys())
            keys = per_property.keys()
            if not all(key in field_names for key in keys):
                missing_keys = [key for key in keys if key not in field_names]
                raise ValueError(
                    f"Property not found in model: {', '.join(missing_keys)}"
                )

            return per_property

        def __init__(self, **data):
            """Called after validation. Sets the fallback for every property that
            has not been specified in per_property."""
            super().__init__(**data)
            per_property_ = {}
            if self.per_property is not None:
                per_property_ = self.per_property
            self._per_property = {
                field_name: per_property_.get(field_name, self.overwrite)
                for field_name in self.model.__fields__.keys()
            }
            # todo: from class definition get properties with hidden /
            #  read_only option  #  those can be safely overwritten - set the to True

    class _ApplyOverwriteParam(OswBaseModel):
        page: WtPage
        entity: OswBaseModel  # actually model.Entity but this causes the "type" error
        policy: Union[OSW.OverwriteClassParam, OVERWRITE_CLASS_OPTIONS]
        namespace: Optional[str]
        meta_category_title: Optional[str]
        meta_category_template_str: Optional[str]
        inplace: Optional[bool] = False
        debug: Optional[bool] = False

        class Config:
            arbitrary_types_allowed = True

        @validator("entity")
        def validate_entity(cls, entity, values):
            """Make sure that the passed entity has the same uuid as the page"""
            page: WtPage = values.get("page")
            if not page.exists:  # Guard clause
                return entity
            jsondata = page.get_slot_content("jsondata")
            if jsondata is None:  # Guard clause
                title = title_from_full_title(page.title)
                try:
                    uuid_from_title = get_uuid(title)
                except ValueError:
                    print(
                        f"Error: UUID could not be determined from title: '{title}', "
                        f"nor fromjsondata: {jsondata}"
                    )
                    return entity
                if str(uuid_from_title) != str(entity.uuid):
                    raise ValueError(
                        f"UUID mismatch: Page UUID: {uuid_from_title}, "
                        f"Entity UUID: {entity.uuid}"
                    )
                return entity
            page_uuid = str(jsondata.get("uuid"))
            entity_uuid = str(getattr(entity, "uuid", None))
            if page_uuid != entity_uuid or page_uuid == str(None):
                # Comparing string type UUIDs
                raise ValueError(
                    f"UUID mismatch: Page UUID: {page_uuid}, Entity UUID: {entity_uuid}"
                )
            return entity

        def __init__(self, **data):
            super().__init__(**data)
            if self.namespace is None:
                self.namespace = get_namespace(self.entity)
            if self.namespace is None:
                raise ValueError("Namespace could not be determined.")
            if not isinstance(self.policy, OSW.OverwriteClassParam):
                self.policy = OSW.OverwriteClassParam(
                    model=self.entity.__class__,
                    overwrite=self.policy,
                )

    @staticmethod
    def _apply_overwrite_policy(param: OSW._ApplyOverwriteParam) -> WtPage:
        if param.inplace:
            page = param.page
        else:
            page = deepcopy(param.page)
        entity_title = f"{param.namespace}:{get_title(param.entity)}"

        def set_content(content_to_set: dict) -> None:
            if param.debug:
                print(f"content_to_set: {str(content_to_set)}")
            for slot_ in content_to_set.keys():
                page.set_slot_content(slot_, content_to_set[slot_])

        # Create a variable to hold the new content
        new_content = {  # required for json parsing and header rendering
            "header": "{{#invoke:Entity|header}}",  # required for footer rendering
            "footer": "{{#invoke:Entity|footer}}",
        }
        # Take the shortcut if
        # 1. page does not exist AND any setting of overwrite
        # 2. overwrite is "replace remote"
        if (
            not page.exists
            or param.policy.overwrite == AddOverwriteClassOptions.replace_remote
        ):
            # Use pydantic serialization, skip none values:
            new_content["jsondata"] = json.loads(param.entity.json(exclude_none=True))
            set_content(new_content)
            page.changed = True
            return page  # Guard clause --> exit function
        # 3. pages does exist AND overwrite is "keep existing"
        if (
            page.exists
            and param.policy.overwrite == AddOverwriteClassOptions.keep_existing
        ):
            print(
                f"Entity '{entity_title}' already exists and won't be stored "
                f"with overwrite set to 'keep existing'!"
            )
            return page  # Guard clause --> exit function
        # Apply the overwrite logic in any other case
        # 4. If per_property was None  -> overwrite will be used as a fallback
        # 4.1 If overwrite is True ---> overwrite existing properties
        # 4.2 If overwrite is False --> don't overwrite existing properties
        # 4.3 If overwrite is "only empty" --> overwrite existing properties if
        #     they are empty
        # * Download page
        # * Merge slots selectively based on per_property

        # Create variables to hold local and remote content prior to merging
        local_content = {}
        remote_content = {}
        # Get the remote content
        for slot in ["jsondata", "header", "footer"]:  # SLOTS:
            remote_content[slot] = page.get_slot_content(
                slot
            )  # Todo: remote content does not contain properties that are not set
        if remote_content["header"]:  # not None or {} or ""
            new_content["header"] = remote_content["header"]
        if remote_content["footer"]:
            new_content["footer"] = remote_content["footer"]
        if param.debug:
            print(f"'remote_content': {str(remote_content)}")
        # Get the local content
        # Properties that are not set in the local content will be set to None
        # We want those not to be listed as keys
        local_content["jsondata"] = json.loads(param.entity.json(exclude_none=True))
        if param.debug:
            print(f"'local_content': {str(remote_content)}")
        # Apply the overwrite logic
        # a) If there is a key in the remote content that is not in the local
        #    content, we have to keep it
        new_content["jsondata"] = remote_content["jsondata"]
        # new_content["jsondata"] = {
        #     key: value
        #     for (key, value) in remote_content["jsondata"].items()
        #     if key not in local_content["jsondata"].keys()
        # }
        if param.debug:
            print(f"'New content' after 'remote' update: {str(new_content)}")
        # b) If there is a key in the local content that is not in the remote
        #    content, we have to keep it
        new_content["jsondata"].update(
            {
                key: value
                for (key, value) in local_content["jsondata"].items()
                if key not in remote_content["jsondata"].keys()
            }
        )
        if param.debug:
            print(f"'New content' after 'local' update: {str(new_content)}")
        # c) If there is a key in both contents, we have to apply the overwrite
        #    logic
        # todo: include logic for hidden and read_only properties!
        new_content["jsondata"].update(
            {
                key: value
                for (key, value) in local_content["jsondata"].items()
                if param.policy._per_property.get(key) == OverwriteOptions.true
            }
        )
        if param.debug:
            print(f"'New content' after 'True' update: {str(new_content)}")
        new_content["jsondata"].update(
            {
                key: value
                for (key, value) in remote_content["jsondata"].items()
                if param.policy._per_property.get(key) == OverwriteOptions.false
            }
        )
        if param.debug:
            print(f"'New content' after 'False' update: {str(new_content)}")
        new_content["jsondata"].update(
            {
                key: value
                for (key, value) in local_content["jsondata"].items()
                if (
                    param.policy._per_property.get(key) == OverwriteOptions.only_empty
                    and is_empty(remote_content["jsondata"].get(key))
                )
            }
        )
        if param.debug:
            print(f"'New content' after 'only empty' update: {str(new_content)}")
            print(f"'New content' to be stored: {str(new_content)}")
        set_content(new_content)
        return page  # Guard clause --> exit function

    class StoreEntityParam(OswBaseModel):
        entities: Union[OswBaseModel, List[OswBaseModel]]  # actually model.Entity
        """The entities to store. Can be a single entity or a list of entities."""
        namespace: Optional[str]
        """The namespace of the entities. If not set, the namespace is derived from the
        entity."""
        parallel: Optional[bool] = None
        """If set to True, the entities are stored in parallel."""
        overwrite: Optional[OVERWRITE_CLASS_OPTIONS] = "keep existing"
        """If no class specific overwrite setting is set, this setting is used."""
        overwrite_per_class: Optional[List[OSW.OverwriteClassParam]] = None
        """A list of OverwriteClassParam objects. If a class specific overwrite setting
        is set, this setting is used.
        """
        meta_category_title: Optional[str] = "Category:Category"
        debug: Optional[bool] = False
        _overwrite_per_class: Dict[str, Dict[str, OSW.OverwriteClassParam]] = (
            PrivateAttr()
        )
        """Private attribute, for internal use only. Use 'overwrite_per_class'
        instead."""

        def __init__(self, **data):
            super().__init__(**data)
            if not isinstance(self.entities, list):
                self.entities = [self.entities]
            if len(self.entities) > 5 and self.parallel is None:
                self.parallel = True
            if self.parallel is None:
                self.parallel = (
                    True  # Set to True after implementation of asynchronous upload
                )
            if self.overwrite is None:
                self.overwrite = self.__fields__["overwrite"].default
            self._overwrite_per_class = {"by name": {}, "by type": {}}
            if self.overwrite_per_class is not None:
                for param in self.overwrite_per_class:
                    model_name = param.model.__name__
                    model_type = param.model.__fields__["type"].default[0]
                    if (
                        model_name in self._overwrite_per_class["by name"].keys()
                        or model_type in self._overwrite_per_class["by type"].keys()
                    ):
                        raise ValueError(
                            f"More than one OverwriteClassParam for the class "
                            f"'{model_type}' ({model_name}) has been passed in the "
                            f"list to 'overwrite_per_class'!"
                        )
                    self._overwrite_per_class["by name"][model_name] = param
                    self._overwrite_per_class["by type"][model_type] = param

    def store_entity(
        self, param: Union[StoreEntityParam, OswBaseModel, List[OswBaseModel]]
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

        param: OSW.StoreEntityParam = param

        max_index = len(param.entities)

        meta_category = self.site.get_page(
            WtSite.GetPageParam(titles=[param.meta_category_title])
        ).pages[0]
        # ToDo: we have to do this iteratively to support meta categories inheritance
        meta_category_template_str = meta_category.get_slot_content("schema_template")
        meta_category_template = None
        if param.namespace == "Category":
            if param.meta_category_title:
                meta_category = self.site.get_page(
                    WtSite.GetPageParam(titles=[param.meta_category_title])
                ).pages[0]
                meta_category_template_str = meta_category.get_slot_content(
                    "schema_template"
                )
            if meta_category_template_str:
                meta_category_template = compile_handlebars_template(
                    meta_category_template_str
                )

        def store_entity_(
            entity_: model.Entity,
            namespace_: str = None,
            index: int = None,
            overwrite_class_param: OSW.OverwriteClassParam = None,
        ) -> None:
            title_ = get_title(entity_)
            if namespace_ is None:
                namespace_ = get_namespace(entity_)
            if namespace_ is None or title_ is None:
                print("Error: Unsupported entity type")
                return
            if overwrite_class_param is None:
                raise TypeError("'overwrite_class_param' must not be None!")
            entity_title = namespace_ + ":" + title_
            page = self._apply_overwrite_policy(
                OSW._ApplyOverwriteParam(
                    page=WtPage(wtSite=self.site, title=entity_title),
                    entity=entity_,
                    namespace=namespace_,
                    policy=overwrite_class_param,
                    meta_category_template_str=meta_category_template_str,
                    debug=param.debug,
                )
            )
            if meta_category_template:
                try:
                    schema_str = eval_compiled_handlebars_template(
                        meta_category_template,
                        page.get_slot_content("jsondata"),
                        {
                            "_page_title": entity_title,  # legacy
                            "_current_subject_": entity_title,
                        },
                    )
                    schema = json.loads(schema_str)
                    # put generated schema in definitions section
                    # currently only enabled for Characteristics
                    if hasattr(model, "CharacteristicType") and isinstance(
                        entity_, model.CharacteristicType
                    ):
                        new_schema = {
                            "$defs": {"generated": schema},
                            "allOf": [{"$ref": "#/$defs/generated"}],
                            "@context": schema.pop("@context", None),
                            "title": schema.pop("title", ""),
                        }
                        schema["title"] = "Generated" + new_schema["title"]
                        schema = new_schema
                    page.set_slot_content("jsonschema", new_schema)
                except Exception as e:
                    print(f"Schema generation from template failed for {entity_}: {e}")
            page.edit()  # will set page.changed if the content of the page has changed
            if page.changed:
                if index is None:
                    print(f"Entity stored at '{page.get_url()}'.")
                else:
                    print(
                        f"({index + 1}/{max_index}) Entity stored at "
                        f"'{page.get_url()}'."
                    )

        sorted_entities = OSW.sort_list_of_entities_by_class(param.entities)
        print(
            "Entities to be uploaded have been sorted according to their type.\n"
            "If you would like to overwrite existing entities or properties, "
            "pass a StoreEntityParam to store_entity() with "
            "attribute 'overwrite' or 'overwrite_per_class' set to, e.g., "
            "True."
        )

        class UploadObject(BaseModel):
            entity: OswBaseModel
            # Actually model.Entity but this causes the "type" error
            namespace: Optional[str]
            index: int
            overwrite_class_param: OSW.OverwriteClassParam

        upload_object_list: List[UploadObject] = []

        upload_index = 0
        for class_type, entities in sorted_entities.by_type.items():
            # Try to get a class specific overwrite setting
            class_param = param._overwrite_per_class["by type"].get(class_type, None)
            if class_param is None:
                entity_model = entities[0].__class__
                class_param = OSW.OverwriteClassParam(
                    model=entity_model,
                    overwrite=param.overwrite,
                )
                if param.debug:
                    print(
                        f"Now adding entities of class type '{class_type}' "
                        f"({entity_model.__name__}) to upload list. No class specific"
                        f" overwrite setting found. Using fallback option '"
                        f"{param.overwrite}' for all entities of this class."
                    )
            for entity in entities:
                upload_object_list.append(
                    UploadObject(
                        entity=entity,
                        namespace=param.namespace,
                        index=upload_index,
                        overwrite_class_param=class_param,
                    )
                )
                upload_index += 1

        def handle_upload_object_(upload_object: UploadObject) -> None:
            store_entity_(
                upload_object.entity,
                upload_object.namespace,
                upload_object.index,
                upload_object.overwrite_class_param,
            )

        if param.parallel:
            _ = parallelize(
                handle_upload_object_, upload_object_list, flush_at_end=param.debug
            )
        else:
            _ = [
                handle_upload_object_(upload_object)
                for upload_object in upload_object_list
            ]

    class DeleteEntityParam(OswBaseModel):
        entities: Union[OswBaseModel, List[OswBaseModel]]
        comment: Optional[str] = None
        parallel: Optional[bool] = None
        debug: Optional[bool] = False

        def __init__(self, **data):
            super().__init__(**data)
            if not isinstance(self.entities, list):
                self.entities = [self.entities]
            if len(self.entities) > 5 and self.parallel is None:
                self.parallel = True
            if self.parallel is None:
                self.parallel = False

    def delete_entity(
        self, entity: Union[OswBaseModel, DeleteEntityParam], comment: str = None
    ):
        """Deletes the given entity/entities from the OSW instance."""
        if not isinstance(entity, OSW.DeleteEntityParam):
            entity = OSW.DeleteEntityParam(entities=entity)
        if comment is not None:
            entity.comment = comment

        def delete_entity_(entity, comment_: str = None):
            """Deletes the given entity from the OSW instance.

            Parameters
            ----------
            entity:
                The dataclass instance to delete
            comment_:
                Command for the change log, by default None
            """
            title_ = None
            namespace_ = None
            if hasattr(entity, "meta"):
                if entity.meta and entity.meta.wiki_page:
                    if entity.meta.wiki_page.title:
                        title_ = entity.meta.wiki_page.title
                    if entity.meta.wiki_page.namespace:
                        namespace_ = entity.meta.wiki_page.namespace
            if namespace_ is None:
                namespace_ = get_namespace(entity)
            if title_ is None:
                title_ = OSW.get_osw_id(entity.uuid)
            if namespace_ is None or title_ is None:
                print("Error: Unsupported entity type")
                return
            entity_title = namespace_ + ":" + title_
            page = self.site.get_page(WtSite.GetPageParam(titles=[entity_title])).pages[
                0
            ]

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

    class QueryInstancesParam(OswBaseModel):
        categories: Union[Union[str, OswBaseModel], List[Union[str, OswBaseModel]]]
        parallel: Optional[bool] = None
        debug: Optional[bool] = False
        limit: Optional[int] = 1000
        _category_string_parts: List[Dict[str, str]] = PrivateAttr()
        _titles: List[str] = PrivateAttr()

        @staticmethod
        def get_full_page_name_parts(
            category_: Union[str, OswBaseModel]
        ) -> Dict[str, str]:
            error_msg = (
                f"Category must be a string like 'Category:<category name>' or a "
                f"dataclass instance with a 'type' attribute. This error occurred on "
                f"'{str(category_)}'"
            )
            if isinstance(category_, str):
                string_to_split = category_
            elif isinstance(category_, OswBaseModel):
                type_ = getattr(category_, "type", None)
                if type_ is None:
                    raise TypeError(error_msg)
                string_to_split = type_[0]
            else:
                raise TypeError(error_msg)
            if "Category:" not in string_to_split:
                raise TypeError(error_msg)
            return {
                "namespace": string_to_split.split(":")[0],
                "title": string_to_split.split(":")[-1],
            }

        def __init__(self, **data):
            super().__init__(**data)
            if not isinstance(self.categories, list):
                self.categories = [self.categories]
            if len(self.categories) > 5 and self.parallel is None:
                self.parallel = True
            if self.parallel is None:
                self.parallel = False
            self._category_string_parts = [
                OSW.QueryInstancesParam.get_full_page_name_parts(cat)
                for cat in self.categories
            ]
            self._titles = [parts["title"] for parts in self._category_string_parts]

    def query_instances(
        self, category: Union[str, OswBaseModel, OSW.QueryInstancesParam]
    ) -> List[str]:
        if not isinstance(category, OSW.QueryInstancesParam):
            category = OSW.QueryInstancesParam(categories=category)
        page_titles = category._titles
        search_param = SearchParam(
            query=[f"[[HasType::Category:{page_title}]]" for page_title in page_titles],
            **category.dict(
                exclude={"categories", "_category_string_parts", "_titles"}
            ),
        )
        full_page_titles = self.site.semantic_search(search_param)
        return full_page_titles

    class JsonLdMode(str, Enum):
        """enum for jsonld processing mode"""

        expand = "expand"
        flatten = "flatten"
        compact = "compact"
        frame = "frame"

    class ExportJsonLdParams(OswBaseModel):
        context_loader_config: Optional[WtSite.JsonLdContextLoaderParams] = None
        """The configuration for the JSON-LD context loader."""
        entities: Union[OswBaseModel, List[OswBaseModel]]
        """The entities to convert to JSON-LD. Can be a single entity or a list of
        entities."""
        resolve_context: Optional[bool] = True
        """If True, remote context URLs are resolved."""
        mode: Optional[OSW.JsonLdMode] = "expand"
        """The JSON-LD processing mode to apply if resolve_context is True."""
        context: Optional[Union[str, list, Dict[str, Any]]] = None
        """The JSON-LD context to apply. Replaces any existing context."""
        additional_context: Optional[Union[str, list, Dict[str, Any]]] = None
        """The JSON-LD context to apply on top of the existing context."""
        frame: Optional[Dict[str, Any]] = None
        """The JSON-LD frame to use for framed mode. If not set, the existing context is used"""
        build_rdf_graph: Optional[bool] = False
        """If True, the output is a graph."""
        debug: Optional[bool] = False

        def __init__(self, **data):
            super().__init__(**data)
            if not isinstance(self.entities, list):
                self.entities = [self.entities]

    class ExportJsonLdResult(OswBaseModel):
        documents: List[Union[Dict[str, Any]]]
        """A single JSON-LD document per entity"""
        graph_document: Dict[str, Any] = None
        """A single JSON-LD document with a @graph element containing all entities"""
        graph: rdflib.Graph = None
        """RDF graph containing all entities. Build only if build_rdf_graph is True"""

        class Config:
            arbitrary_types_allowed = True

    def export_jsonld(self, params: ExportJsonLdParams) -> ExportJsonLdResult:
        """Exports the given entity/entities as JSON-LD."""

        if params.resolve_context:
            jsonld.set_document_loader(
                self.site.get_jsonld_context_loader(params.context_loader_config)
            )

        documents = []
        graph_document = {"@graph": []}
        graph = None
        if params.build_rdf_graph:
            graph = rdflib.Graph()
            prefixes = self.site.get_prefix_dict()
            for prefix in prefixes:
                graph.bind(prefix, prefixes[prefix])

        for e in params.entities:
            data = json.loads(e.json(exclude_none=True, indent=4, ensure_ascii=False))

            data["@context"] = []
            if params.context is None:
                for t in e.type:
                    data["@context"].append("/wiki/" + t)
                if params.context is not None:
                    data["@context"].append(params.context)
            else:
                data["@context"] = {
                    **self.site.get_jsonld_context_prefixes(),
                    **params.context,
                }
            if params.additional_context is not None:
                if data["@context"] is None:
                    data["@context"] = []
                elif not isinstance(data["@context"], list):
                    data["@context"] = [data["@context"]]
                data["@context"].append(params.additional_context)

            data["@id"] = get_full_title(e)

            if params.resolve_context:
                graph_document["@graph"].append(jsonld.expand(data))
                if params.mode == "expand":
                    data = jsonld.expand(data)
                    if isinstance(data, list):
                        data = data[0]
                elif params.mode == "flatten":
                    data = jsonld.flatten(data)
                elif params.mode == "compact":
                    # data = jsonld.expand(data)
                    # if isinstance(data, list): data = data[0]
                    data = jsonld.compact(
                        data,
                        data["@context"] if params.context is None else params.context,
                    )
                elif params.mode == "frame":
                    data = jsonld.frame(
                        data,
                        (
                            {"@context": data["@context"]}
                            if params.frame is None
                            else params.frame
                        ),
                    )

                if params.build_rdf_graph:
                    graph.parse(data=json.dumps(data), format="json-ld")

            documents.append(data)

        result = OSW.ExportJsonLdResult(
            documents=documents, graph_document=graph_document, graph=graph
        )
        return result


OSW._ApplyOverwriteParam.update_forward_refs()
OSW.StoreEntityParam.update_forward_refs()
OSW.ExportJsonLdParams.update_forward_refs()
