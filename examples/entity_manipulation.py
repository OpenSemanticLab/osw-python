import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) #add parent dir to path

from src.osl import OSL, OslClassMetaclass
#import src.osl as osl
from src.wtsite import WtSite
from pprint import pprint 

#from src.model.KB.Entity import *
import src.model.KB.Entity as model
from importlib import reload
from datetime import date

from pydantic import BaseModel, Field
from typing import Optional

#create/update the password file under examples/wiki-admin.pwd
pwd_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml")
wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)
osl = OSL(site = wtsite)

#mycat = Category(uuid = "b02b21b5-b1b3-479e-afc1-2c71ac35a0c1", name="MyCat")
#pprint(mycat)
#osl.sync(mycat)

do_fetch = True
do_fetch = False

if do_fetch:
    #osl.fetch_schema() #this will load the current entity schema from the OSL instance. You may have to re-run the script to get the updated schema extension. Requires 'pip install datamodel-code-generator'
    osl.fetch_schema(OSL.FetchSchemaParam(schema_title="JsonSchema:LIMS/Device/Type", mode='replace'))
    osl.fetch_schema(OSL.FetchSchemaParam(schema_title="JsonSchema:LIMS/Device/Instance", mode='append'))
    #from src.model.KB.Entity import *
    reload(model) #only for modules

#check if the schema extension was loaded
try: model.Device
except AttributeError:
    print("[Ex] Device not defined")
else:
    print("[Ex] Device defined")

#device = model.Device(manufacturer="Test")
#event = model.Event(start=date.fromisoformat("2022-01-01"))
#entity = model.Entity(label="TestE", extensions=[
#     model.Device(
#        manufacturer = "TestM"
#    ),
#    event
#])

#pprint(entity)
#osl.store_entity(entity = entity, entity_title="Term:OSL9c64c51bd5fb4162bc1fa9e60468a09d" )

entity2 = osl.load_entity("Term:OSL9c64c51bd5fb4162bc1fa9e60468a09e")
pprint(entity2)

#create custom model
#@model._basemodel_decorator
#class MyModel(model.BaseModel, metaclass=OslClassMetaclass, osl_template="MyTemplate", osl_footer_template="MyFooterTemplate"):
#    my_property_2: Optional[str]
#    my_property: Optional[int] =  Field(None, title="My Property")

#print(MyModel.schema_json(indent=4))
#myModel = model.Entity(label="MyModel", extensions=[MyModel(my_property=1)])
#pprint(myModel)
#osl.register_schema(OSL.SchemaRegistration(model_cls=MyModel, schema_name="MyModel"))

#import src.model.LIMS.Device.Type as model2
dt = model.DeviceType(label=model.Label(label_text="Test"))
#pprint(dt)
#pprint(dt.json())

se = model.DeviceInstance(
        label="PCB",
        statements=[
            model.Statement(predicate='Contains', object='Gold'),
            model.Statement(predicate='Contains', object='Lead', substatements=[
                model.Statement(predicate="HasConcentration", object="10%")
            ])
        ] 
    )
pprint(se.dict())
osl.store_entity(entity = se, entity_title="Term:OSL9c64c51bd5fb4162bc1fa9e60468a09e" )
