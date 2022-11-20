import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) #add parent dir to path

from src.osl import OSL
#import src.osl as osl
from src.wtsite import WtSite
from pprint import pprint 

#from src.model.KB.Entity import *
import src.model.KB.Entity as model
from importlib import reload

wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", "examples/wiki-admin.pwd") 
osl = OSL(site = wtsite)

#mycat = Category(uuid = "b02b21b5-b1b3-479e-afc1-2c71ac35a0c1", name="MyCat")
#pprint(mycat)
#osl.sync(mycat)

osl.fetch_schema() #this will load the current entity schema from the OSL instance. You may have to re-run the script to get the updated schema extension
#from src.model.KB.Entity import *
reload(model) #only for modules

#check if the schema extension was loaded
try: model.Device
except AttributeError:
    print("[Ex] Device not defined")
else:
    print("[Ex] Device defined")

device = model.Device(manufacturer=2)
entity = model.Entity(label = "Test", extensions=[
     model.Device(manufacturer = "TestM")
])

#pprint(entity._template)
#pprint(entity.dict(include={'_template': True}))
pprint(entity)
osl.store_entity(entity = entity, entity_title="Term:OSL9c64c51bd5fb4162bc1fa9e60468a09d" )

entity2 = osl.load_entity("Term:OSL9c64c51bd5fb4162bc1fa9e60468a09d")
pprint(entity2)