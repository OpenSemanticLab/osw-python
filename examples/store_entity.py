import sys
import os
from pprint import pprint

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) #add parent dir to path

from src.osl import OSL
from src.wtsite import WtSite

import src.model.KB.Entity as model

#create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = "./accounts.pwd.yaml"
wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)
osl = OSL(site = wtsite)

my_entity = model.Entity(label=model.Label(label_text="MyEntity"), statements=[model.Statement(predicate="IsA")])
osl.store_entity(my_entity)