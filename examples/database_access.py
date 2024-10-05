import os

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.express import OswExpress

# Create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)
# pwd_file_path = "./accounts.pwd.yaml"
osw_obj = OswExpress(
    domain="wiki-dev.open-semantic-lab.org", cred_filepath=pwd_file_path
)

# load dependencies
DEPENDENCIES = {
    "Host": "Category:OSW02590972aeba46d7864ed492c0c11384",
    "DatabaseServer": "Category:OSWacdb001c926c46b998af3e645d36b13f",
    "Database": "Category:OSW51ad0d1716254c77a2b7a03217f23b43",
    "DatabaseType": "Category:OSW33c7c3a4076a4a58b20d818c162e84e6",
}
osw_obj.install_dependencies(DEPENDENCIES, mode="append")

# Make sure to import controllers after updating the model (ignore linter warning)
import osw.controller as controller  # noqa: E402

# Load database definition
db = osw_obj.load_entity("Item:OSWb8cc7705e17c47b19331fdb045bfbca8")  # postgres
db = db.cast(model.Database)

# Cast into controller and execute function
db = db.cast(controller.DatabaseController)
db.connect(
    controller.DatabaseController.ConnectionConfig(
        cm=CredentialManager(cred_filepath=pwd_file_path), osw=osw_obj
    )
)
db.execute("SELECT * FROM public.sensors ORDER BY sensor_id ASC")
