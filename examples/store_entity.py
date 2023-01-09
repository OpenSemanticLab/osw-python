import sys
import os

from pprint import pprint
from typing import ClassVar
from uuid import uuid4

from pydantic import BaseModel

from osw.osl import OSL
from osw.wtsite import WtSite

import osw.model.Entity as model

#create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml")
wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)
osl = OSL(site = wtsite)

my_entity = model.Item(label=model.Label(text="MyItem"), statements=[model.Statement(predicate="IsA")])
pprint(my_entity)

osl.store_entity(my_entity)

my_entity2 = osl.load_entity("Item:" + OSL.get_osl_id(my_entity.uuid))
pprint(my_entity)

osl.delete_entity(my_entity)