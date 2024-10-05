import os

from osw.express import OswExpress

# Create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)
# pwd_file_path = "./accounts.pwd.yaml"
osw_obj = OswExpress(
    domain="wiki-dev.open-semantic-lab.org", cred_filepath=pwd_file_path
)

# osw.fetch_schema()  # This will load the current entity schema from the OSW instance.
# You may have to re-run the script to get the updated schema extension.
# Requires 'pip install datamodel-code-generator'
DEPENDENCIES = {
    "Entity": "Category:Entity",
    "Item": "Category:Item",
    # "User": "Category:OSWd9aa0bca9b0040d8af6f5c091bf9eec7",
    # "Group": "Category:OSWb8b6278763d54b0784eea9d3b3d183a4",
    # "Location": "Category:OSW3d238d05316e45a4ac95a11d7b24e36b",
    # "Site": "Category:OSW473d7a1ed48544d1be83b258b5810948",
    # "Building": "Category:OSW4bcd4a99a73f482ea40ac4210dfab836",
    # "Floor": "Category:OSW6c4212f1a39342be963d2b9efd19c5c2",
    # "Room": "Category:OSWc5ed0ed1e33c4b31887c67af25a610c1",
}
osw_obj.install_dependencies(DEPENDENCIES, mode="append")
