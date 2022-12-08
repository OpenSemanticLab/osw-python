from __future__ import annotations

import sys
from enum import Enum
from pprint import pprint
import copy
import types
from uuid import UUID

from jsonpath_ng.ext import parse
from abc import ABCMeta, abstractmethod
from pydantic import BaseModel, Field
from pydantic.main import ModelMetaclass
from typing import ForwardRef, List, Optional, Any, Union, Literal
import datetime
from copy import deepcopy
import os
import json
import importlib
import re

from src.wtsite import WtSite, WtPage
import src.wiki_tools as wt
import src.model.Entity as model

#class DeviceInstance(model.DeviceInstance):
#    def print(self):
#        print("CONTROLLER" + str(self.label))

class AbstractEntity(BaseModel):
    name: str
    uuid: str
    ns: str
    title: Optional[str] = None

class OslClassMetaclass(ModelMetaclass):
    def __new__(cls, name, bases, dic, osl_template, osl_footer_template):
        base_footer_cls = type(dic['__qualname__'] + "Footer", (BaseModel,),
            {
                '__annotations__': {"osl_template": str},
                "osl_template": Field(default=osl_footer_template, title=dic['__qualname__'] + "FooterTemplate")
            }
        )
        if not '__annotations__' in dic: dic['__annotations__'] = {}
        dic['__annotations__']['osl_template'] = str
        dic['osl_template'] = Field(default=osl_template, title=dic['__qualname__'] + "Template")
        dic['__annotations__']['osl_footer'] = base_footer_cls
        dic['osl_footer'] =  Field(default={"osl_template": osl_footer_template}, title=dic['__qualname__'] + "Footer")
        new_cls = super().__new__(cls, name, bases, dic)
        return new_cls

class OSL(BaseModel):
    """OSL Class
    """    
    uuid: str = "2ea5b605-c91f-4e5a-9559-3dff79fdd4a5"
    _protected_keywords = ('_osl_template', '_osl_footer') #private properties included in model export
    class Config:
        arbitrary_types_allowed = True #neccessary to allow e.g. np.array as type
    site: WtSite

    def sync(self, entity: AbstractEntity):
        if not entity.title: entity.title = entity.ns + ":OSL" + entity.uuid.replace('-', '');
        wtpage = self.site.get_WtPage(entity.title)
        
        pprint(wtpage)

    @staticmethod
    def get_osl_id(uuid: uuid) -> str:
        return 'OSL' + str(uuid).replace('-', '')

    @staticmethod
    def get_uuid(osl_id) -> uuid:
        return UUID(osl_id.replace('OSL', ''))

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
            arbitrary_types_allowed = True #allow any class as type
        model_cls: ModelMetaclass
        schema_name: str
        schema_bases: List[str] = ["Entity"]

    def register_schema(self, schema_registration: SchemaRegistration):
        """registers a new or updated schema in OSL

        Parameters
        ----------
        schema_registration
            see SchemaRegistration
        """        
        page = self.site.get_WtPage("JsonSchema:" + schema_registration.schema_name)

        schema = json.loads(schema_registration.model_cls.schema_json(indent=4).replace("$ref", "dollarref"))
        jsonpath_expr = parse('$..allOf')
        #replace local definitions (#/definitions/...) with embedded definitions to prevent resolve errors in json-editor
        for match in jsonpath_expr.find(schema):
            result_array = []
            for subschema in match.value:
                pprint(subschema)
                value = subschema['dollarref']
                if value.startswith('#'):
                    definition_jsonpath_expr = parse(value.replace('#','$').replace('/','.'))
                    for def_match in definition_jsonpath_expr.find(schema):
                        pprint(def_match.value)
                        result_array.append(def_match.value)
                else: result_array.append(subschema)
            match.full_path.update_or_create(schema, result_array)
        if 'definitions' in schema: del schema['definitions']

        #replace 'osl_footer': {'allOf': [{...}]} with 'osl_footer': {...}
        if 'allOf' in schema['properties']['osl_footer']: schema['properties']['osl_footer'] = schema['properties']['osl_footer']['allOf'][0] #directy attach single definition 
        schema['properties']['osl_footer']['options'] = {"hidden": True} #don't show this field in the json-editor
        if not 'required' in schema['properties']['osl_footer']: schema['properties']['osl_footer']['required'] = [] #add required property if missing
        schema['properties']['osl_footer']['required'].extend(['osl_template'])

        schema['properties']['osl_template']['options'] = {"hidden": True} #don't show this field in the json-editor
        schema['properties']['osl_template']['enum'] = [schema['properties']['osl_template']['default']] #a single-value enum represents a constant / literal

        if not 'required' in schema: schema['required'] = []  #add required property if missing
        schema['required'].extend(['osl_template', 'osl_footer']) 

        pprint(schema)

        page.set_content(json.dumps(schema, indent=4).replace("dollarref", "$ref"))
        page.edit("Create / update schema from pydantic BaseModel")
        for base in schema_registration.schema_bases:
            page = self.site.get_WtPage("JsonSchema:" + base)
            schema = json.loads(page.get_content())
            refs = schema['properties']['extensions']['items']['oneOf']
            #pprint(refs)
            schema_url = '/wiki/JsonSchema:' + schema_registration.schema_name + '?action=raw'
            missing = True
            for ref in refs:
                if ref['$ref'] == schema_url: missing = False
            print(missing)
            if missing: refs.append({'$ref': schema_url})
            #pprint(schema)
            page.set_content(json.dumps(schema, indent=4))
            page.edit("add extension schema " + schema_registration.schema_name)

    class FetchSchemaMode(Enum):
        append = "append" #append to the current model
        replace = "replace" #replace the current model

    @model._basemodel_decorator
    class FetchSchemaParam(BaseModel):
        schema_title: Optional[str] = "JsonSchema:Entity"
        root: Optional[bool] = True
        mode: Optional[str] = 'replace' #type 'FetchSchemaMode' requires: 'from __future__ import annotations'

    def fetch_schema(self, fetchSchemaParam: FetchSchemaParam = None):
        if fetchSchemaParam == None: fetchSchemaParam = OSL.FetchSchemaParam()
        schema_title = fetchSchemaParam.schema_title
        root = fetchSchemaParam.root
        schema_name = schema_title.split(':')[-1]
        page = self.site.get_WtPage(schema_title)
        schema = json.loads(page._content.replace("$ref", "dollarref")) # '$' is a special char for root object in jsonpath
        print(f"Fetch {schema_title}")

        jsonpath_expr = parse("$..dollarref")
        for match in jsonpath_expr.find(schema):
            #value = "https://" + self.site._site.host + match.value
            if match.value.startswith('#'): continue #skip self references
            ref_schema_title = match.value.replace("/wiki/","").split('?')[0]
            ref_schema_name = ref_schema_title.split(':')[-1] + ".json"
            value = ""
            for i in range (0, schema_name.count('/')): value += "../" #created relative path to top-level schema dir
            value += ref_schema_name #create a reference to a local file
            match.full_path.update_or_create(schema, value)
            #print(f"replace {match.value} with {value}")
            if (ref_schema_title != schema_title): #prevent recursion in case of self references
                 self.fetch_schema(OSL.FetchSchemaParam(schema_title = ref_schema_title, root = False)) #resolve references recursive

        model_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),"model") #src/model
        schema_path = os.path.join(model_dir_path, schema_name + ".json")
        os.makedirs(os.path.dirname(schema_path), exist_ok=True)
        with open(schema_path, 'w', encoding='utf-8') as f:
            schema_str = json.dumps(schema, ensure_ascii=False, indent=4).replace("dollarref", "$ref")
            #print(schema_str)
            f.write(schema_str)

        #result_model_path = schema_path.replace(".json", ".py")
        result_model_path = os.path.join(model_dir_path, "Entity.py")
        temp_model_path = os.path.join(model_dir_path, "temp.py")
        if (root):
            exec_path = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "datamodel-codegen")
            os.system(f"{exec_path}  --input {schema_path} --input-file-type jsonschema --output {temp_model_path} \
                --base-class OslBaseModel \
                --use-default \
                --enum-field-as-literal one \
                --use-title-as-name \
                --use-schema-description \
                --use-field-description \
            ")
            #see https://koxudaxi.github.io/datamodel-code-generator/
            #--base-class OslBaseModel: use a custom base class
            #--custom-template-dir src/model/template_data/ 
            #--extra-template-data src/model/template_data/extra.json 
            #--use-default: Use default value even if a field is required
            #--enum-field-as-literal one: for static properties like osl_template
            #--use-schema-description: Use schema description to populate class docstring
            #--use-field-description: Use schema description to populate field docstring
            #--use-title-as-name: use titles as class names of models, e. g. for the footer templates

            #this is dirty, but required for autocompletion: https://stackoverflow.com/questions/62884543/pydantic-autocompletion-in-vs-code
            #idealy solved by custom templates in the future: https://github.com/koxudaxi/datamodel-code-generator/issues/860

            content = ""
            with open (temp_model_path, 'r' ) as f:    
                    content = f.read()
            os.remove(temp_model_path)

            content = re.sub(r"(import OslBaseModel)", "from pydantic import BaseModel", content, 1) #remove import statement

            if fetchSchemaParam.mode == 'replace':

                header = (  "from uuid import uuid4\n"
                            "from typing import TYPE_CHECKING\n"
                            "\n"
                            "if TYPE_CHECKING:\n"
                            "    from dataclasses import dataclass as _basemodel_decorator\n"
                            "else:\n"
                            "    _basemodel_decorator = lambda x: x\n"
                            "\n"
                        )
                header += (
                    "\nclass OslBaseModel(BaseModel):\n"
                    "    def full_dict(self, **kwargs): #extent BaseClass export function\n"
                    "        d = super().dict(**kwargs)\n"
                    "        for key in " + str(self._protected_keywords) + ":\n"
                    "            if hasattr(self, key): d[key] = getattr(self, key) #include selected private properites. note: private properties are not considered as discriminator \n"
                    "        return d\n"
                )


                content = re.sub(r"(class\s*\S*\s*\(\s*OslBaseModel\s*\)\s*:.*\n)", header + r"\n\n\n\1", content, 1) #replace first match
                content = re.sub(r"(class\s*\S*\s*\(\s*OslBaseModel\s*\)\s*:.*\n)", r"@_basemodel_decorator\n\1", content)
                content = re.sub(r"(UUID = Field\(...)", r"UUID = Field(default_factory=uuid4", content) #enable default value for uuid
                with open (result_model_path, 'w' ) as f:    
                    f.write(content)

            if fetchSchemaParam.mode == 'append':
                org_content = ""
                with open (result_model_path, 'r' ) as f:    
                    org_content = f.read()

                pattern = re.compile(r"class\s*([\S]*)\s*\(\s*\S*\s*\)\s*:.*\n") #match class definition [\s\S]*(?:[^\S\n]*\n){2,}
                for (cls) in re.findall(pattern, org_content):
                    print(cls)
                    content = re.sub(r"(class\s*" + cls + r"\s*\(\s*\S*\s*\)\s*:.*\n[\s\S]*?(?:[^\S\n]*\n){2,})", "", content, count=1) #replace duplicated classes

                content = re.sub(r"(from __future__ import annotations)", "", content, 1) #remove import statement
                #print(content)
                with open (result_model_path, 'a' ) as f:    
                    f.write(content)

            importlib.reload(model) #reload the updated module

    def load_entity(self, entity_title):
        page = self.site.get_WtPage(entity_title)
        osl_schema = 'JsonSchema:Entity'
        for key in page._dict[0]:
            if 'osl_schema' in page._dict[0][key]: osl_schema = page._dict[0][key]['osl_schema']
        #cls = osl_schema.split(':')[1].split('/')[-1] #better use schema['title]
        schema_str = self.site.get_WtPage(osl_schema).get_content()
        schema = json.loads(schema_str.replace("$ref", "dollarref"))
        cls = schema['title']
        #print(cls)
        full_schema_str = eval(f"model.{cls}.schema_json(indent=4)")
        full_schema = json.loads(full_schema_str.replace("$ref", "dollarref"))
        #print(full_schema_str)
        
        schema_json = wt.wikiJson2SchemaJson(full_schema, page._dict)
        pprint(schema_json)
        try:
            model.Device
        except AttributeError:
            print("Device not defined")
        else:
            print("Device defined")

        entity = None
        #entity =  model.Entity(**schema_json)
        #exec(f"entity = model.{cls}(**schema_json)")
        entity = eval(f"model.{cls}(**schema_json)")

        return entity

    def store_entity(self, entity: model.Entity) -> None:
        entity_title = "Term:" + OSL.get_osl_id(entity.uuid)
        page = self.site.get_WtPage(entity_title)
        schema_json = entity.full_dict()
        #print(json)
        wiki_json = wt.schemaJson2WikiJson(schema_json)
        #print(wiki_json)
        page._dict = wiki_json
        page.update_content()
        #print(page.get_content())
        page.edit()
        print("Entity stored at " + page.get_url())
    
class AbstractCategory(AbstractEntity):
    ns: str = "Category"

thing = AbstractCategory(uuid = "9fa9e361-dc72-4e50-8f2c-0990620459e8", title="Thing", name="Thing")

class Category(AbstractCategory):
    wt: str = "LIMS/Category/Software"
    #super_category: 'Category' = 'Category'(uuid = "9fa9e361-dc72-4e50-8f2c-0990620459e8", title="Thing", name="Thing")
    super_category: Optional[AbstractCategory] = thing
Category.update_forward_refs()
    
class SoftwareCategory(Category):
    wt: str = "LIMS/Category/Software"

class AbstractInformationalProcess(AbstractEntity):
    name: str
    uuid: str
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
        
    @abstractmethod
    def apply(self, obj, param):
        pass  
