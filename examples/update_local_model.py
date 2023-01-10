import os
from importlib import reload

import osw.model.Entity as model
from osw.osl import OSL
from osw.wtsite import WtSite

# create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)
# pwd_file_path = "./accounts.pwd.yaml"
wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)
osl = OSL(site=wtsite)

# osl.fetch_schema() #this will load the current entity schema from the OSL instance. You may have to re-run the script to get the updated schema extension. Requires 'pip install datamodel-code-generator'
osl.fetch_schema(OSL.FetchSchemaParam(schema_title="Category:Hardware", mode="replace"))
osl.fetch_schema(
    OSL.FetchSchemaParam(
        schema_title="Category:OSLf9742b744112486ea2a5d8afee3e2538", mode="append"
    )
)
reload(model)
