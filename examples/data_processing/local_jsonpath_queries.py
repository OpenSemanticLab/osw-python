import os
from pprint import pprint
from typing import List, Optional

from jsonpath_ng.ext import parse

import osw.model.entity as model
from osw.core import OSW
from osw.wtsite import WtSite

# create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "accounts.pwd.yaml"
)
# pwd_file_path = "./accounts.pwd.yaml"
wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)
osw = OSW(site=wtsite)

entities_dict = {}  # helper dict for jsonpath queries


# target class
class SomeItem(model.Item):
    type: List[str] = ["Category:Item"]
    custom_attribute: Optional[str]


# helper class
class CustomItem(SomeItem):
    internal_id: str


# construct dict from semantic query
# entities = wtsite.semantic_search("[[HasType::Category:Item]]")
# for entity in entities: entities_dict[entity] = {'jsondata': osw.load_entity(entity).json(exclude_none=True)}

# manually create test data
e1 = CustomItem(label=[model.Label(text="Item1")], internal_id="001")
e2 = CustomItem(
    label=[model.Label(text="Item2")], internal_id="002", custom_attribute="001"
)
entities = [e1, e2]

print("\nInitial data with internal IDs:")
for e in entities:
    print(e.cast(SomeItem).json(exclude_none=True))  # casting strips 'internal_id'
    entities_dict[str(e.uuid)] = {}
    entities_dict[str(e.uuid)]["jsondata"] = e.dict(
        exclude_none=True
    )  # query does not work without intermediate attribute 'jsondata'

print("\nHelper dict")
pprint(entities_dict)

print("\nProcessed data with global IDs:")
for e in entities:
    jsonpath_internal_id_match = parse(f'*[?internal_id = "{e.custom_attribute}"]')
    matches = jsonpath_internal_id_match.find(entities_dict)
    if len(matches) > 0:
        e.custom_attribute = str(
            matches[0].value["uuid"]
        )  # replace internal id with uuid
    if len(matches) > 1:
        print(
            "Warning: Multiple matches for "
            + f'*[?internal_id = "{e.custom_attribute}"]'
        )
    print(e.cast(SomeItem).json(exclude_none=True))  # casting strips 'internal_id'
