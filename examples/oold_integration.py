import json
import os
from uuid import UUID

import osw.model.entity as model
from osw.express import OswExpress

# Create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)
# pwd_file_path = "./accounts.pwd.yaml"
# create OSW instance which auto-registers as a oold backend
osw_obj = OswExpress(
    domain="wiki-dev.open-semantic-lab.org", cred_filepath=pwd_file_path
)

# create an instance of a keyword and store it
k = model.Keyword(
    uuid=UUID("dcb75346-cf24-4793-bdb8-0c6fd68ebc2c"),
    label=[model.Label(text="Test Keyword", lang="en")],
    description=[model.Description(text="Test Description", lang="en")],
)
k.store_jsonld()

# create an instance of an item linked to the keyword and store it
# the keyword will be stored by its IRI ("Item:OSWdcb75346cf244793bdb80c6fd68ebc2c")
i = model.Item(
    uuid=UUID("c65b130f-8aca-4d29-b1fd-6aef488759a6"),
    label=[model.Label(text="Test Item for OOLD Integration", lang="en")],
    keywords=[k],
)
assert i.label[0].text == "Test Item for OOLD Integration"
jsonld_export = json.loads(i.json())
assert jsonld_export["keywords"][0] == "Item:OSWdcb75346cf244793bdb80c6fd68ebc2c"
i.store_jsonld()

# load the item again by its IRI
i_ = model.Item[i.get_iri()]
assert i_.uuid == i.uuid

# accessing the keyword property auto-resolves the keyword iri via the oold backend
assert i_.keywords[0].label[0].text == "Test Keyword"
