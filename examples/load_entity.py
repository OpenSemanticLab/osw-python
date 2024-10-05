import os

import osw.model.entity as model
from osw.express import OswExpress

# Create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)
# pwd_file_path = "./accounts.pwd.yaml"
osw_obj = OswExpress(
    domain="wiki-dev.open-semantic-lab.org", cred_filepath=pwd_file_path
)

# Load Tutorial Schema on demand
if not hasattr(model, "Tutorial"):
    DEPENDENCIES = {"Tutorial": "Category:OSW494f660e6a714a1a9681c517bbb975da"}
    osw_obj.install_dependencies(DEPENDENCIES, mode="replace")

# Load instance HowToCreateANewArticle
title = "Item:OSW52c2c5a6bbc84fcb8eab0fa69857e7dc"
entity = osw_obj.load_entity(title)
print(entity.__class__)
print(entity.label[0].text)  # We can access any attribute of model.Entity

tutorial_entity = entity.cast(model.Tutorial)  # Explicit cast to model.Tutorial
print(
    tutorial_entity.required_predecessor
)  # We can access now any attribute of model.Tutorial

print(entity.json(exclude_none=True))  # export as json

# Load all instances of Tutorial in parallel
tutorials = osw_obj.query_instances(
    category="Category:OSW494f660e6a714a1a9681c517bbb975da"
)
print(tutorials)
osw_obj.load_entity(tutorials)
