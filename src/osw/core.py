from __future__ import annotations

import importlib
import json
import logging
import os
import pathlib
import re
import warnings
from copy import deepcopy
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union, overload
from uuid import UUID, uuid4
from warnings import warn

import black
import datamodel_code_generator
import isort
import rdflib
from jsonpath_ng.ext import parse
from mwclient.client import Site
from oold.backend.interface import (
    Backend,
    ResolveParam,
    ResolveResult,
    SetBackendParam,
    SetResolverParam,
    StoreParam,
    StoreResult,
    set_backend,
    set_resolver,
)
from oold.generator import Generator
from oold.utils.codegen import OOLDJsonSchemaParser
from opensemantic.v1 import OswBaseModel
from pydantic import PydanticDeprecatedSince20
from pydantic.v1 import BaseModel, Field, PrivateAttr, create_model, validator
from pyld import jsonld

import osw.model.entity as model
from osw.defaults import params as default_params
from osw.utils.code_postprocessing import remove_constraints_from_forward_refs
from osw.utils.oold import (
    AggregateGeneratedSchemasParam,
    AggregateGeneratedSchemasParamMode,
    aggregate_generated_schemas,
    escape_json_strings,
    merge_generated_definitions,
)
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
    remove_empty,
    title_from_full_title,
)
from osw.wiki_tools import SearchParam
from osw.wtsite import WtPage, WtSite

_logger = logging.getLogger(__name__)


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

    def __init__(self, **data: Any):
        super().__init__(**data)

        # implement resolver backend with osw.load_entity
        class OswDefaultBackend(Backend):

            # oold.backend.interface is pydantic v2, so we cannot use
            # our v1 OSW model as attribute directly
            osw_obj: Any

            def resolve_iris(self, iris: List[str]) -> dict[str, dict]:
                pass

            def resolve(self, request: ResolveParam):
                # print("RESOLVE", request)
                osw_obj: OSW = self.osw_obj
                entities = osw_obj.load_entity(
                    OSW.LoadEntityParam(titles=request.iris)
                ).entities
                # create a dict with request.iris as keys and the loaded entities as values
                # by iterating over both lists
                nodes = {}
                for iri, entity in zip(request.iris, entities):
                    nodes[iri] = entity
                return ResolveResult(nodes=nodes)

            def store_jsonld_dicts(self, jsonld_dicts):
                pass

            def store(self, request: StoreParam):
                osw_obj: OSW = self.osw_obj
                osw_obj.store_entity(
                    OSW.StoreEntityParam(
                        entities=list(request.nodes.values()), overwrite=True
                    ),
                )
                return StoreResult(success=True)

            def query():
                pass

        r = OswDefaultBackend(osw_obj=self)
        set_resolver(SetResolverParam(iri="Item", resolver=r))
        set_resolver(SetResolverParam(iri="Category", resolver=r))
        set_resolver(SetResolverParam(iri="Property", resolver=r))
        set_resolver(SetResolverParam(iri="File", resolver=r))
        set_backend(SetBackendParam(iri="Item", backend=r))
        set_backend(SetBackendParam(iri="Category", backend=r))
        set_backend(SetBackendParam(iri="Property", backend=r))
        set_backend(SetBackendParam(iri="File", backend=r))

    @property
    def mw_site(self) -> Site:
        """Returns the mwclient Site object of the OSW instance."""
        return self.site.mw_site

    def close_connection(self):
        """Close the connection to the OSL instance."""
        self.mw_site.connection.close()

    @staticmethod
    def get_osw_id(uuid: Union[str, UUID]) -> str:
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
    def get_uuid(osw_id: str) -> UUID:
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
                model_type = entity.__class__.__fields__["type"].get_default()[0]
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
        """dataclass param of register_schema()"""

        class Config:
            arbitrary_types_allowed = True  # allow any class as type

        model_cls: Type[OswBaseModel]
        """The model class"""
        schema_uuid: str  # Optional[str] = model_cls.__uuid__
        """The schema uuid"""
        schema_name: str  # Optional[str] = model_cls.__name__
        """The schema name"""
        schema_bases: List[str] = Field(default=["Category:Item"])
        """A list of base schemas (referenced by allOf)"""

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
        """dataclass param of register_schema()"""

        class Config:
            arbitrary_types_allowed = True  # allow any class as type

        model_cls: Optional[Type[OswBaseModel]]
        """The model class"""
        model_uuid: Optional[str]
        """The model uuid"""
        comment: Optional[str]
        """The comment for the deletion, to be left behind"""

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
        generate_annotations: Optional[bool] = True
        """generate custom schema keywords in Fields and Classes.
        Required to update the schema in OSW without information loss"""
        generator_options: Optional[Dict[str, Any]] = None
        """custom options for the datamodel-code-generator"""
        offline_pages: Optional[Dict[str, WtPage]] = None
        """pages to be used offline instead of fetching them from the OSW instance"""
        result_model_path: Optional[Union[str, pathlib.Path]] = None
        """path to the generated model file, if None,
        the default path ./model/entity.py is used"""

        class Config:
            arbitrary_types_allowed = True

    class FetchSchemaResult(BaseModel):
        fetched_schema_titles: Optional[List[str]] = None
        """List of titles of the schemas that were fetched.
        This includes the requested schemas and their dependencies."""
        error_messages: Optional[List[str]] = None
        """List of critical errors that did interrupt the fetch process"""
        warning_messages: Optional[List[str]] = None
        """List of warnings that did not interrupt the fetch process"""

    def fetch_schema(
        self, fetchSchemaParam: FetchSchemaParam = None
    ) -> FetchSchemaResult:
        """Loads the given schemas from the OSW instance and auto-generates python
        datasclasses within osw.model.entity from it

        Parameters
        ----------
        fetchSchemaParam
            See FetchSchemaParam, by default None
        """
        if not isinstance(fetchSchemaParam.schema_title, list):
            fetchSchemaParam.schema_title = [fetchSchemaParam.schema_title]
        first = True
        last = False
        results = []
        for schema_title in fetchSchemaParam.schema_title:
            last = schema_title == fetchSchemaParam.schema_title[-1]
            mode = fetchSchemaParam.mode
            if not first:  # 'replace' makes only sense for the first schema
                mode = "append"
            res = self._fetch_schema(
                OSW._FetchSchemaParam(
                    schema_title=schema_title,
                    mode=mode,
                    final=last,
                    generate_annotations=fetchSchemaParam.generate_annotations,
                    generator_options=fetchSchemaParam.generator_options,
                    offline_pages=fetchSchemaParam.offline_pages,
                    result_model_path=fetchSchemaParam.result_model_path,
                )
            )
            results.append(res)
            first = False

        # merge unique results and return
        merged_result = OSW.FetchSchemaResult(
            fetched_schema_titles=[], error_messages=[]
        )
        for result in results:
            if result.fetched_schema_titles:
                merged_result.fetched_schema_titles.extend(result.fetched_schema_titles)
            if result.error_messages:
                merged_result.error_messages.extend(result.error_messages)
        return OSW.FetchSchemaResult(
            fetched_schema_titles=(
                list(set(merged_result.fetched_schema_titles))
                if len(merged_result.fetched_schema_titles) > 0
                else None
            ),
            error_messages=(
                list(set(merged_result.error_messages))
                if len(merged_result.error_messages) > 0
                else None
            ),
        )

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
        """marks the root iteration for a recursive fetch (internal param, default: True)"""
        final: Optional[bool] = True
        """if multiple schemas are fetched this marks the final run to cleanup the code"""
        mode: Optional[str] = (
            "replace"
            # type 'FetchSchemaMode' requires: 'from __future__ import annotations'
        )
        generate_annotations: Optional[bool] = False
        """generate custom schema keywords in Fields and Classes.
        Required to update the schema in OSW without information loss"""
        generator_options: Optional[Dict[str, Any]] = None
        """custom options for the datamodel-code-generator"""
        offline_pages: Optional[Dict[str, WtPage]] = None
        """pages to be used offline instead of fetching them from the OSW instance"""
        result_model_path: Optional[Union[str, pathlib.Path]] = None
        """path to the generated model file, if None,
        the default path ./model/entity.py is used"""
        fetched_schema_titles: Optional[List[str]] = []
        """keep track of fetched schema titles to prevent recursion"""
        warning_messages: Optional[List[str]] = None

        class Config:
            arbitrary_types_allowed = True

    def _fetch_schema(
        self, fetchSchemaParam: _FetchSchemaParam = None
    ) -> FetchSchemaResult:
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
        fetchSchemaParam.fetched_schema_titles.append(schema_title)
        root = fetchSchemaParam.root
        schema_name = schema_title.split(":")[-1]
        if (
            fetchSchemaParam.offline_pages is not None
            and schema_title in fetchSchemaParam.offline_pages
        ):
            print(f"Fetch {schema_title} from offline pages")
            page = fetchSchemaParam.offline_pages[schema_title]
        else:
            print(f"Fetch {schema_title} from online pages")
            page = self.site.get_page(WtSite.GetPageParam(titles=[schema_title])).pages[
                0
            ]
            if not page.exists:
                print(f"Error: Page {schema_title} does not exist")
                return OSW.FetchSchemaResult(
                    fetched_schema_titles=fetchSchemaParam.fetched_schema_titles,
                    warning_messages=fetchSchemaParam.warning_messages,
                    error_messages=[f"Page {schema_title} does not exist"],
                )
        # not only in the JsonSchema namespace the schema is located in the main slot
        # in all other namespaces, the json_schema slot is used
        if schema_title.startswith("JsonSchema:"):
            schema_str = ""
            if page.get_slot_content("main"):
                schema_str = json.dumps(page.get_slot_content("main"))
        else:
            schema_str = ""
            if page.get_slot_content("jsonschema"):
                schema = merge_generated_definitions(
                    deepcopy(page.get_slot_content("jsonschema"))
                )
                schema_str = json.dumps(schema)
        if (schema_str is None) or (schema_str == ""):
            print(f"Warning: Schema slot of {schema_title} is empty")
            schema_str = "{}"  # empty schema to make reference work
            if fetchSchemaParam.warning_messages is None:
                fetchSchemaParam.warning_messages = []
            fetchSchemaParam.warning_messages.append(
                f"Schema slot of {schema_title} is empty"
            )

        generator = Generator()
        schemas_for_preprocessing = [json.loads(schema_str)]
        generator.preprocess(
            Generator.GenerateParams(json_schemas=schemas_for_preprocessing)
        )
        schema_str = json.dumps(schemas_for_preprocessing[0])

        schema = json.loads(schema_str.replace("$ref", "dollarref"))

        jsonpath_expr = parse("$..dollarref")
        for match in jsonpath_expr.find(schema):
            # value = "https://" + self.mw_site.host + match.value
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
                and ref_schema_title not in fetchSchemaParam.fetched_schema_titles
            ):  # prevent recursion in case of self references
                _param = fetchSchemaParam.copy()
                _param.root = False
                _param.schema_title = ref_schema_title
                self._fetch_schema(_param)  # resolve references recursive

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
        if fetchSchemaParam.result_model_path:
            result_model_path = fetchSchemaParam.result_model_path
            if not isinstance(result_model_path, str):
                result_model_path = str(result_model_path)
        temp_model_path = os.path.join(model_dir_path, "temp.py")
        data_model_type = "pydantic.BaseModel"
        if fetchSchemaParam.generator_options is not None:
            data_model_type = fetchSchemaParam.generator_options.get(
                "output_model_type", "pydantic.BaseModel"
            )
        if root:
            # suppress deprecation warnings from pydantic
            # see https://github.com/koxudaxi/datamodel-code-generator/issues/2213
            warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)

            if fetchSchemaParam.generate_annotations:
                # monkey patch class
                datamodel_code_generator.parser.jsonschema.JsonSchemaParser = (
                    OOLDJsonSchemaParser
                )
            datamodel_code_generator.generate(
                input_=pathlib.Path(schema_path),
                input_file_type="jsonschema",
                output=pathlib.Path(temp_model_path),
                base_class=(
                    "opensemantic.v1.OswBaseModel"
                    if data_model_type == "pydantic.BaseModel"
                    else "opensemantic.OswBaseModel"
                ),
                # use_default=True,
                apply_default_values_for_required_fields=True,
                use_unique_items_as_set=True,
                enum_field_as_literal=datamodel_code_generator.LiteralType.Off,
                # will create MyEnum(str, Enum) instead of MyEnum(Enum)
                use_subclass_enum=True,
                set_default_enum_member=True,
                use_title_as_name=True,
                use_schema_description=True,
                use_field_description=True,
                encoding="utf-8",
                use_double_quotes=True,
                collapse_root_models=True,
                reuse_model=True,
                field_include_all_keys=True,
                allof_class_hierarchy=datamodel_code_generator.AllOfClassHierarchy.Always,
                additional_imports=(
                    ["uuid.uuid4", "pydantic.ConfigDict"]
                    if data_model_type != "pydantic.BaseModel"
                    else ["uuid.uuid4"]
                ),
                **(fetchSchemaParam.generator_options or {}),
            )

            # note: we could use OOLDJsonSchemaParser directly (see below),
            # but datamodel_code_generator.generate
            # does some pre- and postprocessing we do not want to duplicate

            # data_model_type = datamodel_code_generator.DataModelType.PydanticBaseModel
            # #data_model_type = DataModelType.PydanticV2BaseModel
            # target_python_version = datamodel_code_generator.PythonVersion.PY_38
            # data_model_types = datamodel_code_generator.model.get_data_model_types(
            #   data_model_type, target_python_version
            # )
            # parser = OOLDJsonSchemaParserFixedRefs(
            #     source=pathlib.Path(schema_path),

            #     base_class="opensemantic.OswBaseModel",
            #     data_model_type=data_model_types.data_model,
            #     data_model_root_type=data_model_types.root_model,
            #     data_model_field_type=data_model_types.field_model,
            #     data_type_manager_type=data_model_types.data_type_manager,
            #     target_python_version=target_python_version,

            #     #use_default=True,
            #     apply_default_values_for_required_fields=True,
            #     use_unique_items_as_set=True,
            #     enum_field_as_literal=datamodel_code_generator.LiteralType.All,
            #     use_title_as_name=True,
            #     use_schema_description=True,
            #     use_field_description=True,
            #     encoding="utf-8",
            #     use_double_quotes=True,
            #     collapse_root_models=True,
            #     reuse_model=True,
            #     #field_include_all_keys=True
            # )
            # result = parser.parse()
            # with open(temp_model_path, "w", encoding="utf-8") as f:
            #     f.write(result)

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
            # only if generator_options["data_model_type"] is not set or "pydantic.BaseModel"
            if data_model_type == "pydantic.BaseModel":
                content = re.sub(
                    r"(from pydantic import)", "from pydantic.v1 import", content
                )

            # remove field param unique_items
            # --use-unique-items-as-set still keeps unique_items=True as Field param
            # which was removed, see https://github.com/pydantic/pydantic-core/issues/296
            # --output-model-type pydantic_v2.BaseModel fixes that but generated models
            # are not v1 compatible mainly by using update_model()
            content = re.sub(r"(,?\s*unique_items=True\s*)", "", content)

            # Detect empty subclasses, replaces their occurrences with base classes,
            # and removes the empty class definitions.
            # Only processes subclasses that follow naming patterns:
            # - BaseclassModel (e.g., DescriptionModel extends Description)
            # - Baseclass<number> (e.g., Label1, Label2 extend Label)

            # Pattern to match empty subclasses
            # Matches: class SubClass(BaseClass):
            # followed by optional whitespace/docstring and pass
            pattern = "".join(
                (
                    r"class\s+",  # 'class' keyword
                    r"(\w+)",  # capture subclass name
                    r"\s*\(\s*",  # opening parenthesis
                    r"(\w+)",  # capture base class name
                    r"\s*\)\s*:",  # closing parenthesis and colon
                    r"\s*",  # optional whitespace
                    r'(?:\n\s*(?:""".*?"""|\'\'\'.*?\'\'\')'
                    # optional docstring (triple quotes)
                    r"\s*)?",  # end optional docstring
                    r"\n\s*pass\s*",  # pass statement
                    r"(?:\n|$)",  # newline or end of string
                )
            )

            # Find all empty subclasses
            matches = list(re.finditer(pattern, content, re.MULTILINE | re.DOTALL))

            # Filter matches based on naming patterns
            valid_matches = []
            for match in matches:
                subclass_name = match.group(1)
                base_class_name = match.group(2)

                # Check if subclass follows the naming patterns
                if (
                    subclass_name == base_class_name + "Model"  # BaseclassModel pattern
                    or re.match(
                        rf"^{re.escape(base_class_name)}\d+$", subclass_name
                    )  # Baseclass<number> pattern
                ):
                    valid_matches.append(match)

            content = content
            replacements = []

            # Process matches in reverse order to avoid offset issues when removing
            for match in reversed(valid_matches):
                subclass_name = match.group(1)
                base_class_name = match.group(2)
                replacements.append((subclass_name, base_class_name))

                # Remove the entire class definition
                start, end = match.span()
                # Also remove any trailing newlines to avoid extra blank lines
                while end < len(content) and content[end] == "\n":
                    end += 1

                content = content[:start] + content[end:]

            # Replace all occurrences of subclass names with base class names
            for subclass_name, base_class_name in reversed(replacements):
                pattern_replace = r"\b" + re.escape(subclass_name) + r"\b"
                content = re.sub(pattern_replace, base_class_name, content)

            if fetchSchemaParam.mode == "replace":

                header = "from uuid import uuid4\n"

                # if target path is default model/entity.py, we need to add imports
                if fetchSchemaParam.result_model_path is None:
                    if data_model_type == "pydantic.BaseModel":
                        header += "from opensemantic.core.v1 import (\n"
                    else:
                        header += "from opensemantic.core import (\n"
                    header += (
                        "    Label,\n"
                        "    Entity,\n"
                        "    Item,\n"
                        "    DefinedTerm,\n"
                        "    Keyword,\n"
                        "    IntangibleItem,\n"
                        "    Meta,\n"
                        "    WikiPage,\n"
                        "    LangCode,\n"
                        "    Description,\n"
                        "    ObjectStatement,\n"
                        "    DataStatement,\n"
                        "    QuantityStatement,\n"
                        "    File,\n"
                        "    LocalFile,\n"
                        "    RemoteFile,\n"
                        "    WikiFile,\n"
                        "    PagePackage,\n"
                        ")  # noqa: F401, E402\n"
                        "\n"
                    )

                content = re.sub(
                    pattern=r"(^class\s*\S*\s*\(\s*[\S\s]*?\s*\)\s*:.*\n)",
                    repl=header + r"\n\n\n\1",
                    string=content,
                    count=1,
                    flags=re.MULTILINE,
                )  # add header before first class declaration

            if fetchSchemaParam.mode == "append":
                org_content = ""
                with open(result_model_path, "r", encoding="utf-8") as f:
                    org_content = f.read()

                pattern = re.compile(
                    r"^class\s*([\S]*)\s*\(\s*[\S\s]*?\s*\)\s*:.*\n", re.MULTILINE
                )  # match class definition [\s\S]*(?:[^\S\n]*\n){2,}
                for cls in re.findall(pattern, org_content):
                    content = re.sub(
                        r"^(class\s*"
                        + cls
                        + r"\s*\(\s*[\S\s]*?\s*\)\s*:.*\n[\s\S]*?(?:[^\S\n]*\n){3,})",
                        "",
                        content,
                        count=1,
                        flags=re.MULTILINE,
                    )  # replace duplicated classes

                # combine original and new content
                all_content = org_content + "\n\n\n" + content
                content = all_content

            if fetchSchemaParam.final:
                # Cleanup the combined content
                # find all "<cls>.update_forward_refs()" lines,
                # remove duplicates and put them to EOF
                # do the same for "<cls>.model_rebuild()"
                func_list = []
                if data_model_type == "pydantic.BaseModel":
                    func_list.append("update_forward_refs")
                if data_model_type == "pydantic_v2.BaseModel":
                    func_list.append("model_rebuild")
                for func in func_list:
                    pattern_forward_ref = re.compile(r"(\w+)\." + func + r"\(\s*\)\s*")
                    forward_refs = pattern_forward_ref.findall(content)
                    if forward_refs:
                        # remove all occurrences
                        content = pattern_forward_ref.sub("", content)
                    # add unique occurrences to the end of the file
                    unique_forward_refs = list()
                    for cls in forward_refs:
                        if f"{cls}.{func}()\n" not in unique_forward_refs:
                            unique_forward_refs.append(f"{cls}.{func}()\n")
                    content += "\n" + "".join(sorted(unique_forward_refs))

                # Moves all single-line import statements to the beginning of the file.
                import_pattern = (
                    r"^(?:\s*#\s*[^\n]*\n)?"
                    r"(?:from\s+(\w+(?:\.\w+)*)\s+)?import\s+(?:\w+(?:\s+as\s+\w+)?(?:\s*,\s*\w+(?:\s+as\s+\w+)?)*)"
                    r"|^(?:\s*#\s*[^\n]*\n)?(?:from\s+(\w+(?:\.\w+)*)\s+import\s+\((?:[^\n]*\n?)*?\))\s*(?:#\s*[^\n]*)?$"
                )

                # iterate over the matches
                # collect full import statements to move them to the top
                # replace the original location with an empty string
                imports = []
                for match in re.finditer(import_pattern, content, re.MULTILINE):
                    import_stmt = match.group(0)
                    # # if "from __future__ import annotations" insert at index 0
                    # if import_stmt.strip() == "from __future__ import annotations":
                    #     imports.insert(0, import_stmt)
                    # else:
                    imports.append(import_stmt)
                    # replace all occurrences with empty string
                    # make sure to use match line start and end since import pattern
                    # may overlap partially, e.g.
                    # from datetime import date
                    # from datetime import date, datetime
                    print("Replace import statement:", import_stmt)
                    content = re.sub(
                        r"^" + re.escape(import_stmt) + r"$",
                        "",
                        content,
                        flags=re.MULTILINE,
                    )
                    # remove duplicate imports (done by isort later)
                    imports = list(set(imports))
                # add imports to the beginning of the file
                content = "\n".join(sorted(imports)) + "\n\n" + content

                # remove contrains from ForwardRefs
                content = remove_constraints_from_forward_refs(content)

                # run formatting tool black on the combined content
                # consolidate imports as well
                try:
                    content = black.format_str(content, mode=black.Mode())
                    # run isort to sort imports using Vertical Hanging Indent style
                    content = isort.code(content, profile="black")
                except Exception:
                    pass  # black is optional, continue without formatting

            with open(result_model_path, "w", encoding="utf-8") as f:
                f.write(content)

            if fetchSchemaParam.final:
                importlib.reload(model)  # reload the updated module
                if not site_cache_state:
                    self.site.disable_cache()  # restore original state

        return OSW.FetchSchemaResult(
            fetched_schema_titles=fetchSchemaParam.fetched_schema_titles,
            warning_messages=fetchSchemaParam.warning_messages,
        )

    def install_dependencies(
        self,
        dependencies: Dict[str, str] = None,
        mode: str = "append",
        policy: str = "force",
    ):
        """Installs data models, listed in the dependencies, in the osw.model.entity
        module.

        Parameters
        ----------
        dependencies
            A dictionary with the keys being the names of the dependencies and the
            values being the full page name (IRI) of the dependencies.
        mode
            The mode to use when loading the dependencies. Default is 'append',
            which will keep existing data models and only load the missing ones. The
            mode 'replace' will replace all existing data models with the new ones.
        policy
            The policy to use when loading the dependencies. Default is 'force',
            which will always load the dependencies. If policy is 'if-missing',
            dependencies will only be loaded if they are not already installed.
            This may lead to outdated dependencies, if the dependencies have been
            updated on the server. If policy is 'if-outdated', dependencies will only
            be loaded if they were updated on the server. (not implemented yet)
        """
        if dependencies is None:
            if default_params.dependencies is None:
                raise ValueError(
                    "No 'dependencies' parameter was passed to "
                    "install_dependencies() and "
                    "osw.defaults.params.dependencies was not set!"
                )
            dependencies = default_params.dependencies
        schema_fpts = []
        for k, v in dependencies.items():
            if policy != "if-missing" or not hasattr(model, k):
                schema_fpts.append(v)
            if policy == "if-outdated":
                raise NotImplementedError(
                    "The policy 'if-outdated' is not implemented yet."
                )
        schema_fpts = list(set(schema_fpts))
        for schema_fpt in schema_fpts:
            if not schema_fpt.count(":") == 1:
                raise ValueError(
                    f"Full page title '{schema_fpt}' does not have the correct format. "
                    "It should be 'Namespace:Name'."
                )
        self.fetch_schema(OSW.FetchSchemaParam(schema_title=schema_fpts, mode=mode))

    @staticmethod
    def check_dependencies(dependencies: Dict[str, str]) -> List[str]:
        """Check if the dependencies are installed in the osw.model.entity module.

        Parameters
        ----------
        dependencies
            A dictionary with the keys being the names of the dependencies and the
            values being the full page name (IRI) of the dependencies.
        """
        return [dep for dep in dependencies if not hasattr(model, dep)]

    def ensure_dependencies(self, dependencies: Dict[str, str]):
        """Ensure that the dependencies are installed in the osw.model.entity module.

        Parameters
        ----------
        dependencies
            A dictionary with the keys being the names of the dependencies and the
            values being the full page name (IRI) of the dependencies.
        """
        if self.check_dependencies(dependencies):
            self.install_dependencies(dependencies)

    class LoadEntityParam(BaseModel):
        """Param for load_entity()"""

        titles: Union[str, List[str]]
        """The pages titles to load - one or multiple titles (wiki page name) of
        entities"""
        autofetch_schema: Optional[bool] = True
        """If true, load the corresponding schemas /
        categories ad-hoc if not already present"""
        model_to_use: Optional[Type[OswBaseModel]] = None
        """If provided this model will be used to create an entity (instance of the
        model), instead of instantiating the autofetched schema."""
        remove_empty: Optional[bool] = True
        """If true, remove key with an empty string, list, dict or set as value
        from the jsondata."""
        disable_cache: bool = False
        """If true, disable the cache for the loading process"""
        offline_pages: Optional[Dict[str, WtPage]] = None
        """pages to be used offline instead of fetching them from the OSW instance"""

        class Config:
            arbitrary_types_allowed = True  # allow any class as type

        def __init__(self, **data):
            super().__init__(**data)
            if not isinstance(self.titles, list):
                self.titles = [self.titles]

    class LoadEntityResult(BaseModel):
        """Result of load_entity()"""

        entities: Union[model.Entity, List[model.Entity]]
        """The dataclass instance(s)"""

    # fmt: off
    @overload
    def load_entity(self, entity_title: str) -> model.Entity:
        ...

    @overload
    def load_entity(self, entity_title: List[str]) -> List[model.Entity]:
        ...

    @overload
    def load_entity(self, entity_title: LoadEntityParam) -> LoadEntityResult:
        ...

    # fmt: on

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

        if param.model_to_use:
            print(f"Using schema {param.model_to_use.__name__} to create entity")

        # store original cache state
        cache_state = self.site.get_cache_enabled()
        if param.disable_cache:
            self.site.disable_cache()
        if not cache_state and param.disable_cache:
            # enable cache to speed up loading
            self.site.enable_cache()

        entities = []
        pages = self.site.get_page(
            WtSite.GetPageParam(titles=param.titles, offline_pages=param.offline_pages)
        ).pages
        for page in pages:
            entity = None
            schemas = []
            schemas_fetched = True
            jsondata = page.get_slot_content("jsondata")
            if param.remove_empty:
                remove_empty(jsondata)
            if jsondata:
                for category in jsondata["type"]:
                    schema = (
                        self.site.get_page(
                            WtSite.GetPageParam(
                                titles=[category], offline_pages=param.offline_pages
                            )
                        )
                        .pages[0]
                        .get_slot_content("jsonschema")
                    )
                    schemas.append(schema)
                    # generate model if not already exists
                    cls_name: str = schema["title"]
                    # If a schema_to_use is provided, we do not need to check if the
                    #  model exists
                    if not param.model_to_use:
                        if not hasattr(model, cls_name):
                            if param.autofetch_schema:
                                self.fetch_schema(
                                    OSW.FetchSchemaParam(
                                        schema_title=category,
                                        mode="append",
                                        offline_pages=param.offline_pages,
                                    )
                                )
                        if not hasattr(model, cls_name):
                            schemas_fetched = False
                            print(
                                f"Error: Model {cls_name} not found. Schema {category} "
                                f"needs to be fetched first."
                            )
            if not schemas_fetched:
                continue

            try:
                if param.model_to_use:
                    entity: model.OswBaseModel = param.model_to_use(**jsondata)

                elif len(schemas) == 0:
                    _logger.error("Error: no schema defined")

                elif len(schemas) == 1:
                    cls: Type[model.Entity] = getattr(model, schemas[0]["title"])
                    entity: model.Entity = cls(**jsondata)

                else:
                    bases = []
                    for schema in schemas:
                        bases.append(getattr(model, schema["title"]))
                    cls = create_model("Test", __base__=tuple(bases))
                    entity: model.Entity = cls(**jsondata)
            except Exception as e:
                _logger.error(f"Error creating entity from page {page.title}: {e}")
                entity = None

            if entity is not None:
                # make sure we do not override existing metadata
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
        """A key (property name) - value (overwrite setting) pair."""
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

        def __setattr__(self, key, value):
            """Called when setting an attribute"""
            super().__setattr__(key, value)
            if key == "per_property":
                # compare value and self.per_property
                if value != self.per_property and value is not None:
                    self._per_property = {
                        field_name: value.get(field_name, self.overwrite)
                        for field_name in self.model.__fields__.keys()
                    }
            elif key == "overwrite":
                if self.per_property is not None:
                    self._per_property = {
                        field_name: self.per_property.get(field_name, self.overwrite)
                        for field_name in self.model.__fields__.keys()
                    }
            elif key == "model":
                if self.per_property is not None:
                    self._per_property = {
                        field_name: self.per_property.get(field_name, self.overwrite)
                        for field_name in self.model.__fields__.keys()
                    }

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

        def get_overwrite_setting(self, property_name: str) -> OverwriteOptions:
            """Returns the fallback overwrite option for the given field name"""
            return self._per_property.get(property_name, self.overwrite)

    class _ApplyOverwriteParam(OswBaseModel):
        page: WtPage
        entity: OswBaseModel  # actually model.Entity but this causes the "type" error
        policy: Union[OSW.OverwriteClassParam, OVERWRITE_CLASS_OPTIONS]
        namespace: Optional[str]
        remove_empty: Optional[bool] = True
        inplace: Optional[bool] = False
        debug: Optional[bool] = False
        offline: Optional[bool] = False

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
        new_content = {
            # required for json parsing and header rendering
            "header": "{{#invoke:Entity|header}}",
            # required for footer rendering
            "footer": "{{#invoke:Entity|footer}}",
        }
        # Take the shortcut if
        # 1. page does not exist AND any setting of overwrite
        # 2. overwrite is "replace remote"
        if (
            not page.exists
            or param.policy.overwrite == AddOverwriteClassOptions.replace_remote
            or param.offline is True
        ):
            # Use pydantic serialization, skip none values:
            new_content["jsondata"] = json.loads(param.entity.json(exclude_none=True))
            if param.remove_empty:
                remove_empty(new_content["jsondata"])
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
            remote_content[slot] = page.get_slot_content(slot)
            # Todo: remote content does not contain properties that are not set
        if param.remove_empty:
            remove_empty(remote_content["jsondata"])
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
        if param.remove_empty:
            remove_empty(local_content["jsondata"])
        if param.debug:
            print(f"'local_content': {str(local_content)}")
        # Apply the overwrite logic
        # a) If there is a key in the remote content that is not in the local
        #    content, we have to keep it
        if remote_content["jsondata"] is None:
            remote_content["jsondata"] = {}
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
                if param.policy.get_overwrite_setting(key) == OverwriteOptions.true
            }
        )
        if param.debug:
            print(f"'New content' after 'True' update: {str(new_content)}")
        new_content["jsondata"].update(
            {
                key: value
                for (key, value) in remote_content["jsondata"].items()
                if param.policy.get_overwrite_setting(key) == OverwriteOptions.false
            }
        )
        if param.debug:
            print(f"'New content' after 'False' update: {str(new_content)}")
        new_content["jsondata"].update(
            {
                key: value
                for (key, value) in local_content["jsondata"].items()
                if (
                    param.policy.get_overwrite_setting(key)
                    == OverwriteOptions.only_empty
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
        remove_empty: Optional[bool] = True
        """If true, remove key with an empty string value from the jsondata."""
        change_id: Optional[str] = None
        """ID to document the change. Entities within the same store_entity() call will
        share the same change_id. This parameter can also be used to link multiple
        store_entity() calls."""
        bot_edit: Optional[bool] = True
        """Mark the edit as bot edit,
        which hides the edit from the recent changes in the default filer"""
        edit_comment: Optional[str] = None
        """Additional comment to explain the edit."""
        meta_category_title: Optional[Union[str, List[str]]] = "Category:Category"
        debug: Optional[bool] = False
        offline: Optional[bool] = False
        """If set to True, the processed entities are not upload but only returned as WtPages.
        Can be used to create WtPage objects from entities without uploading them."""
        _overwrite_per_class: Dict[str, Dict[str, OSW.OverwriteClassParam]] = (
            PrivateAttr()
        )
        """Private attribute, for internal use only. Use 'overwrite_per_class'
        instead."""

        def __init__(self, **data):
            super().__init__(**data)
            if not isinstance(self.entities, list):
                self.entities = [self.entities]
            if self.change_id is None:
                self.change_id = str(uuid4())
            for entity in self.entities:
                if getattr(entity, "meta", None) is None:
                    entity.meta = model.Meta()
                if entity.meta.change_id is None:
                    entity.meta.change_id = []
                if self.change_id not in entity.meta.change_id:
                    entity.meta.change_id.append(self.change_id)
            if len(self.entities) > 5 and self.parallel is None:
                self.parallel = True
            if self.parallel is None:
                self.parallel = (
                    True  # Set to True after implementation of asynchronous upload
                )
            if self.overwrite is None:
                self.overwrite = self.__fields__["overwrite"].get_default()
            self._overwrite_per_class = {"by name": {}, "by type": {}}
            if self.overwrite_per_class is not None:
                for param in self.overwrite_per_class:
                    model_name = param.model.__name__
                    model_type = param.model.__fields__["type"].get_default()[0]
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

    class StoreEntityResult(OswBaseModel):
        """Result of store_entity()"""

        change_id: str
        """The ID of the change"""
        pages: Dict[str, WtPage]
        """The pages that have been stored"""

        class Config:
            arbitrary_types_allowed = True

    def store_entity(
        self, param: Union[StoreEntityParam, OswBaseModel, List[OswBaseModel]]
    ) -> StoreEntityResult:
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
        created_pages = {}

        meta_category_templates = {}
        if param.namespace == "Category":
            meta_category_titles = param.meta_category_title
            if not isinstance(meta_category_titles, list):
                meta_category_titles = [meta_category_titles]
            meta_category_template_strs = {}
            # We have to do this iteratively to support meta categories inheritance
            while meta_category_titles is not None and len(meta_category_titles) > 0:
                meta_categories = self.site.get_page(
                    WtSite.GetPageParam(titles=meta_category_titles)
                ).pages
                for meta_category in meta_categories:
                    meta_category_template_strs[meta_category.title] = (
                        meta_category.get_slot_content("schema_template")
                    )

                meta_category_titles = meta_category.get_slot_content("jsondata").get(
                    "subclass_of"
                )

            for title in meta_category_template_strs.keys():
                meta_category_template_str = meta_category_template_strs[title]
                if meta_category_template_str:
                    meta_category_templates[title] = compile_handlebars_template(
                        meta_category_template_str
                    )
            # inverse order to have the most generic template first
            meta_category_templates = dict(reversed(meta_category_templates.items()))

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
                    page=WtPage(
                        wtSite=self.site, title=entity_title, do_init=not param.offline
                    ),
                    entity=entity_,
                    namespace=namespace_,
                    policy=overwrite_class_param,
                    remove_empty=param.remove_empty,
                    debug=param.debug,
                    offline=param.offline,
                )
            )
            if len(meta_category_templates.keys()) > 0:
                generated_schemas = {}
                try:
                    jsondata = page.get_slot_content("jsondata")
                    if param.remove_empty:
                        remove_empty(jsondata)

                    for key in meta_category_templates:
                        meta_category_template = meta_category_templates[key]
                        schema_str = eval_compiled_handlebars_template(
                            meta_category_template,
                            escape_json_strings(jsondata),
                            {
                                "_page_title": entity_title,  # Legacy
                                "_current_subject_": entity_title,
                            },
                        )
                        generated_schemas[key] = json.loads(schema_str)
                except Exception as e:
                    print(f"Schema generation from template failed for {entity_}: {e}")

                mode = AggregateGeneratedSchemasParamMode.ROOT_LEVEL
                # Put generated schema in definitions section,
                #  currently only enabled for Characteristics
                if hasattr(model, "CharacteristicType") and isinstance(
                    entity_, model.CharacteristicType
                ):
                    mode = AggregateGeneratedSchemasParamMode.DEFINITIONS_SECTION

                new_schema = aggregate_generated_schemas(
                    AggregateGeneratedSchemasParam(
                        schema=page.get_slot_content("jsonschema"),
                        generated_schemas=generated_schemas,
                        mode=mode,
                    )
                ).aggregated_schema
                page.set_slot_content("jsonschema", new_schema)
            if param.offline is False:
                page.edit(
                    param.edit_comment, bot_edit=param.bot_edit
                )  # will set page.changed if the content of the page has changed
            if not param.offline and page.changed:
                if index is None:
                    print(f"Entity stored at '{page.get_url()}'.")
                else:
                    print(
                        f"({index + 1}/{max_index}) Entity stored at "
                        f"'{page.get_url()}'."
                    )
            created_pages[page.title] = page

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
        return OSW.StoreEntityResult(change_id=param.change_id, pages=created_pages)

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
        self,
        entity: Union[OswBaseModel, List[OswBaseModel], DeleteEntityParam],
        comment: str = None,
    ):
        """Deletes the given entity/entities from the OSW instance."""
        if not isinstance(entity, OSW.DeleteEntityParam):
            entity = OSW.DeleteEntityParam(entities=entity)
        if comment is not None:
            entity.comment = comment

        def delete_entity_(entity_, comment_: str = None):
            """Deletes the given entity from the OSW instance.

            Parameters
            ----------
            entity_:
                The dataclass instance to delete
            comment_:
                Command for the change log, by default None
            """
            title_ = None
            namespace_ = None
            if hasattr(entity_, "meta"):
                if entity_.meta and entity_.meta.wiki_page:
                    if entity_.meta.wiki_page.title:
                        title_ = entity_.meta.wiki_page.title
                    if entity_.meta.wiki_page.namespace:
                        namespace_ = entity_.meta.wiki_page.namespace
            if namespace_ is None:
                namespace_ = get_namespace(entity_)
            if title_ is None:
                title_ = OSW.get_osw_id(entity_.uuid)
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
        categories: Union[
            Union[str, Type[OswBaseModel]], List[Union[str, Type[OswBaseModel]]]
        ]
        parallel: Optional[bool] = None
        debug: Optional[bool] = False
        limit: Optional[int] = 1000
        _category_string_parts: List[Dict[str, str]] = PrivateAttr()
        _titles: List[str] = PrivateAttr()

        @staticmethod
        def get_full_page_name_parts(
            category_: Union[str, Type[OswBaseModel]]
        ) -> Dict[str, str]:
            error_msg = (
                f"Category must be a string like 'Category:<category name>' or a "
                f"dataclass subclass with a 'type' attribute. This error occurred on "
                f"'{str(category_)}'"
            )
            if isinstance(category_, str):
                string_to_split = category_
            elif issubclass(category_, OswBaseModel):
                type_ = category_.__fields__.get("type")
                if getattr(type_, "default", None) is None:
                    raise TypeError(error_msg)
                string_to_split = type_.default[0]
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
        self, category: Union[str, Type[OswBaseModel], OSW.QueryInstancesParam]
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
        id_keys: Optional[List[str]] = Field(default=["osw_id"])
        """The keys to use as @id in the JSON-LD output. If not found in the entity at root
        level, the full page title is used."""
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
        """If True, debug information is printed."""

        class Config:
            arbitrary_types_allowed = True

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
            if params.id_keys is not None:
                # append "@id" mappings to the context in an additional object
                id_mapping = {}
                for k in params.id_keys:
                    id_mapping[k] = "@id"
                data["@context"].append(id_mapping)
            if params.context is None:
                for t in e.type:
                    data["@context"].append("/wiki/" + t)
                if params.context is not None:
                    data["@context"].append(params.context)
            else:
                data["@context"].append(self.site.get_jsonld_context_prefixes())
                if isinstance(params.context, list):
                    data["@context"].extend(params.context)
                else:
                    data["@context"].append(params.context)
            if params.additional_context is not None:
                if data["@context"] is None:
                    data["@context"] = []
                elif not isinstance(data["@context"], list):
                    data["@context"] = [data["@context"]]
                data["@context"].append(params.additional_context)

            # if none of the id_keys is found, use the full title
            if not any(k in data for k in params.id_keys):
                data["@id"] = get_full_title(e)

            if params.resolve_context:
                graph_document["@graph"].append(jsonld.expand(data))
                if params.mode == "expand":
                    data = jsonld.expand(data)
                    if isinstance(data, list) and len(data) > 0:
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
