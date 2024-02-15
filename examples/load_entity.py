import os

import osw.model.entity as model
from osw.core import OSW
from osw.wtsite import WtSite

# create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)
# pwd_file_path = "./accounts.pwd.yaml"
wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)
osw = OSW(site=wtsite)

title = "Item:OSW7d7193567ea14e4e89b74de88983b718"
# title = "Item:OSWe02213b6c4664d04834355dc8eb08b99"
entity = osw.load_entity(title)
print(entity.__class__)
print(entity.label[0].text)  # we can access any attribute of model.Entity

hardware_entity = entity.cast(model.Hardware)  # explicit cast to model.Hardware
print(hardware_entity.manufacturer)  # we can access now any attribute of model.Entity

print(entity.manufacturer)

print(entity.json(exclude_none=True))
