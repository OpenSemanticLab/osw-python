import os

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.core import OSW
from osw.wtsite import WtSite

# create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)
# pwd_file_path = "./accounts.pwd.yaml"
wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)
osw = OSW(site=wtsite)

wtsite.enable_cache()  # skip downloads on second request

# osw.fetch_schema() #this will load the current entity schema from the OSW instance. You may have to re-run the script to get the updated schema extension. Requires 'pip install datamodel-code-generator'
if True:
    osw.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title="Category:OSW02590972aeba46d7864ed492c0c11384",  # Host
            mode="replace",
        )
    )
    osw.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title="Category:OSWacdb001c926c46b998af3e645d36b13f",
            # DatabaseServer
            mode="append",
        )
    )
    osw.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title="Category:OSW51ad0d1716254c77a2b7a03217f23b43",  # Database
            mode="append",
        )
    )
    osw.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title="Category:OSW33c7c3a4076a4a58b20d818c162e84e6",  # DatabaseType
            mode="append",
        )
    )


# make sure to import controllers after updating the model (ignore linter warning)
import osw.controller as controller  # noqa: E402

# load database definition
db = osw.load_entity("Item:OSWb8cc7705e17c47b19331fdb045bfbca8")  # postgres
db = db.cast(model.Database)

# cast into controller and execute function
db = db.cast(controller.DatabaseController)
db.connect(
    controller.DatabaseController.ConnectionConfig(
        cm=CredentialManager(cred_filepath=pwd_file_path), osw=osw
    )
)
db.execute("SELECT * FROM public.sensors ORDER BY sensor_id ASC")
