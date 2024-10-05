import os
from pprint import pprint

import osw.model.entity as model
from osw.core import OSW
from osw.express import OswExpress

# Create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)
osw_obj = OswExpress(
    domain="wiki-dev.open-semantic-lab.org", cred_filepath=pwd_file_path
)

my_entity = model.Item(
    label=[model.Label(text="MyItem")], statements=[model.Statement(predicate="IsA")]
)
pprint(my_entity)

osw_obj.store_entity(my_entity)

my_entity2 = osw_obj.load_entity("Item:" + OSW.get_osw_id(my_entity.uuid))
pprint(my_entity)

osw_obj.delete_entity(my_entity)
