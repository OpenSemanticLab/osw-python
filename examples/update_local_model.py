import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) #add parent dir to path

from src.osl import OSL
from src.wtsite import WtSite

import src.model.Entity as model
from importlib import reload

#create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml")
#pwd_file_path = "./accounts.pwd.yaml"
wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)
osl = OSL(site = wtsite)

osl.fetch_schema() #this will load the current entity schema from the OSL instance. You may have to re-run the script to get the updated schema extension. Requires 'pip install datamodel-code-generator'
#osl.fetch_schema(OSL.FetchSchemaParam(schema_title="JsonSchema:LIMS/Device/Type", mode='replace'))
#osl.fetch_schema(OSL.FetchSchemaParam(schema_title="JsonSchema:LIMS/Device/Instance", mode='append'))
reload(model)