import os
from importlib import reload
from pprint import pprint

import osw.model.Entity as model
from osw.osl import OSL
from osw.wtsite import WtSite

# import src.controller.DeviceType as crtl
# from src.controller.DeviceType import DeviceInstance


# create/update the password file under examples/wiki-admin.pwd
pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)
wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)
osl = OSL(site=wtsite)

do_fetch = True
do_fetch = False

if do_fetch:
    # osl.fetch_schema() #this will load the current entity schema from the OSL instance. You may have to re-run the script to get the updated schema extension. Requires 'pip install datamodel-code-generator'
    osl.fetch_schema(
        OSL.FetchSchemaParam(schema_title="JsonSchema:LIMS/Device/Type", mode="replace")
    )
    osl.fetch_schema(
        OSL.FetchSchemaParam(
            schema_title="JsonSchema:LIMS/Device/Instance", mode="append"
        )
    )
    reload(model)  # only for modules

# check if the schema extension was loaded
try:
    model.Device
except AttributeError:
    print("[Ex] Device not defined")
else:
    print("[Ex] Device defined")

# device = model.Device(manufacturer="Test")
# event = model.Event(start=date.fromisoformat("2022-01-01"))
# entity = model.Entity(label="TestE", extensions=[
#     model.Device(
#        manufacturer = "TestM"
#    ),
#    event
# ])

# pprint(entity)
# osl.store_entity(entity = entity, entity_title="Term:OSL9c64c51bd5fb4162bc1fa9e60468a09d" )

entity2 = osl.load_entity("Term:OSL9c64c51bd5fb4162bc1fa9e60468a09e")
# pprint(entity2)
print(type(entity2))
# ctrl = crtl.DeviceController(dev = entity2)
# ctrl.print()

entity2.print()
entity2.getPlot()
di = model.DeviceInstance(label="test")
di.print()
print(type(di))

# create custom model
# @model._basemodel_decorator
# class MyModel(model.BaseModel, metaclass=OslClassMetaclass, osl_template="MyTemplate", osl_footer_template="MyFooterTemplate"):
#    my_property_2: Optional[str]
#    my_property: Optional[int] =  Field(None, title="My Property")

# print(MyModel.schema_json(indent=4))
# myModel = model.Entity(label="MyModel", extensions=[MyModel(my_property=1)])
# pprint(myModel)
# osl.register_schema(OSL.SchemaRegistration(model_cls=MyModel, schema_name="MyModel"))

# import src.model.LIMS.Device.Type as model2
dt = model.DeviceType(label=model.Label(label_text="Test"))
# pprint(dt)
# pprint(dt.json())

se = model.DeviceInstance(
    label="PCB",
    statements=[
        model.Statement(predicate="Contains", object="Gold"),
        model.Statement(
            predicate="Contains",
            object="Lead",
            substatements=[model.Statement(predicate="HasConcentration", object="10%")],
        ),
    ],
)
pprint(se.dict())
osl.store_entity(entity=se, entity_title="Term:OSL9c64c51bd5fb4162bc1fa9e60468a09e")
