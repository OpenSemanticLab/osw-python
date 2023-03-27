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

# osw.fetch_schema() #this will load the current entity schema from the OSW instance.
# You may have to re-run the script to get the updated schema extension.
# Requires 'pip install datamodel-code-generator'
list_of_categories = [
    "Category:Entity",
    "Category:Item",
    # "Category:OSWd9aa0bca9b0040d8af6f5c091bf9eec7",  # User
    # "Category:OSWb8b6278763d54b0784eea9d3b3d183a4",  # Group
    # "Category:OSW3d238d05316e45a4ac95a11d7b24e36b",  # Location
    # "Category:OSW473d7a1ed48544d1be83b258b5810948",  # Site
    # "Category:OSW4bcd4a99a73f482ea40ac4210dfab836",  # Building
    # "Category:OSW6c4212f1a39342be963d2b9efd19c5c2",  # Floor
    # "Category:OSWc5ed0ed1e33c4b31887c67af25a610c1",  # Room
]
for i, cat in enumerate(list_of_categories):
    mode = "append"
    if i == 0:
        mode = "replace"
    osw.fetch_schema(OSW.FetchSchemaParam(schema_title=cat, mode=mode))
reload(model)
