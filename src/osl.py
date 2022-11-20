from pprint import pprint
import copy
import types
from jsonpath_ng.ext import parse
from abc import ABCMeta, abstractmethod
from pydantic import BaseModel, validator
from typing import List, Optional, Any, Union
import datetime
from copy import deepcopy
import os
import json
import importlib

from src.wtsite import WtSite, WtPage
import src.wiki_tools as wt
import src.model.KB.Entity as model

class AbstractEntity(BaseModel):
    name: str
    uuid: str
    ns: str
    title: Optional[str] = None

class OSL(BaseModel):
    uuid: str = "2ea5b605-c91f-4e5a-9559-3dff79fdd4a5"
    class Config:
        arbitrary_types_allowed = True #neccessary to allow e.g. np.array as type
    site: WtSite

    def sync(self, entity: AbstractEntity):
        if not entity.title: entity.title = entity.ns + ":OSL" + entity.uuid.replace('-', '');
        wtpage = self.site.get_WtPage(entity.title)
        
        pprint(wtpage)

    def fetch_schema(self, schema_title = "JsonSchema:KB/Entity", root = True):
        schema_name = schema_title.split(':')[-1]
        page = self.site.get_WtPage(schema_title)
        schema = json.loads(page._content.replace("$ref", "dollarref")) # '$' is a special char for root object in jsonpath
        #print(schema)

        jsonpath_expr = parse("$..dollarref")
        for match in jsonpath_expr.find(schema):
            #value = "https://" + self.site._site.host + match.value
            ref_schema_title = match.value.replace("/wiki/","").split('?')[0]
            ref_schema_name = ref_schema_title.split(':')[-1] + ".json"
            value = ""
            for i in range (0, ref_schema_name.count('/')): value += "../" #created relative path to top-level schema dir
            value += ref_schema_name #create a reference to a local file
            match.full_path.update_or_create(schema, value)
            #print(f"replace {match.value} with {value}")
            if (ref_schema_title != schema_title): #prevent recursion in case of self references
                 self.fetch_schema(schema_title = ref_schema_title, root = False) #resolve references recursive

        schema_path = "src/model/" + schema_name + ".json"
        os.makedirs(os.path.dirname(schema_path), exist_ok=True)
        with open(schema_path, 'w', encoding='utf-8') as f:
            schema_str = json.dumps(schema, ensure_ascii=False, indent=4).replace("dollarref", "$ref")
            #print(schema_str)
            f.write(schema_str)

        model_path = schema_path.replace(".json", ".py")
        if (root): 
            os.system(f"datamodel-codegen  --input {schema_path} --input-file-type jsonschema --output {model_path} \
                --use-default \
                --use-title-as-name \
                --use-schema-description \
                --use-field-description \
            ")
        #see https://koxudaxi.github.io/datamodel-code-generator/
        #--use-default: Use default value even if a field is required
        #--use-schema-description: Use schema description to populate class docstring
        #--use-field-description: Use schema description to populate field docstring
        #--use-title-as-name: use titles as class names of models, e. g. for the footer templates

        importlib.reload(model) #reload the updated module

    def load_entity(self, entity_title):
        page = self.site.get_WtPage(entity_title)
        json = wt.wikiJson2SchemaJson(page._dict)
        #pprint(json)
        try:
            model.Device
        except AttributeError:
            print("Device not defined")
        else:
            print("Device defined")
        entity = model.Entity(**json)
        return entity

    def store_entity(self, entity_title, entity):
        page = self.site.get_WtPage(entity_title)
        schema_json = entity.dict()
        #print(json)
        wiki_json = wt.schemaJson2WikiJson(schema_json)
        #print(wiki_json)
        page._dict = wiki_json
        page.update_content()
        page.edit()
    
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
