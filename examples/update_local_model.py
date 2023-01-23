import os
from importlib import reload

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

# osw.fetch_schema() #this will load the current entity schema from the OSW instance. You may have to re-run the script to get the updated schema extension. Requires 'pip install datamodel-code-generator'
osw.fetch_schema(OSW.FetchSchemaParam(schema_title="Category:Hardware", mode="replace"))
osw.fetch_schema(
    OSW.FetchSchemaParam(
        schema_title="Category:OSWf9742b744112486ea2a5d8afee3e2538", mode="append"
    )
)
reload(model)
