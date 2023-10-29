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
wtsite = WtSite(
    config=WtSite.WtSiteConfig(
        iri="wiki-dev.open-semantic-lab.org",
        cred_mngr=CredentialManager(cred_filepath=pwd_file_path),
    )
)
osw = OSW(site=wtsite)

# Load Tutorial Schema on demand
if not hasattr(model, "Tutorial"):
    osw.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title="Category:OSW494f660e6a714a1a9681c517bbb975da", mode="replace"
        )
    )

# load instance HowToCreateANewArticle
title = "Item:OSW52c2c5a6bbc84fcb8eab0fa69857e7dc"
entity = osw.load_entity(title)
print(entity.__class__)
print(entity.label[0].text)  # we can access any attribute of model.Entity

tutorial_entity = entity.cast(model.Tutorial)  # explicit cast to model.Tutorial
print(
    tutorial_entity.required_predecessor
)  # we can access now any attribute of model.Tutorial

print(entity.json(exclude_none=True))  # export as json

# load all instances of Tutorial in parallel
tutorials = osw.query_instances(category="Category:OSW494f660e6a714a1a9681c517bbb975da")
print(tutorials)
osw.load_entity(tutorials)
