import os

from typing_extensions import override

from osw.controller.entity import Entity, Hardware
from osw.express import OswExpress

# Create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)
# pwd_file_path = "./accounts.pwd.yaml"
osw_obj = OswExpress(
    domain="wiki-dev.open-semantic-lab.org", cred_filepath=pwd_file_path
)

# Install dependencies
osw_obj.fetch_schema(
    fetchSchemaParam=OswExpress.FetchSchemaParam(schema_title="Category:Hardware")
)


title = "Item:OSW7d7193567ea14e4e89b74de88983b718"
# title = "Item:OSWe02213b6c4664d04834355dc8eb08b99"
entity = osw_obj.load_entity(title).cast(Entity)
print(entity.__class__)
print(entity.label[0].text)  # We can access any attribute of model.Entity...
entity.explain()  # ...and any methode of controller.Entity

hardware_entity = entity.cast(Hardware)  # Explicitly cast to model.Hardware
print(
    hardware_entity.manufacturer
)  # We can access now any attribute of model.Entity...
hardware_entity.run()  # ...and any methode of controller.Hardware ...
hardware_entity.explain()  # ...and any inherited methode of controller.Entity


# You can also write your own controller
class CustomHardware(Hardware):
    @override
    def run(self):
        super().run()
        print("...but with some custom stuff")

    def a_new_methode(self):
        print("New Stuff")


my_hardware_entity = hardware_entity.cast(CustomHardware)
my_hardware_entity.run()
my_hardware_entity.a_new_methode()
