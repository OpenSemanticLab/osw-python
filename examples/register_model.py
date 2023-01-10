import os
from importlib import reload
from pprint import pprint
from typing import ClassVar
from uuid import uuid4

from pydantic import BaseModel

import osw.model.Entity as model
from osw.osl import OSL
from osw.wtsite import WtSite

# create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)
wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)
osl = OSL(site=wtsite)


class MyClass(
    BaseModel
):  # we don't inherit from model.Item here because this will trigger a full schema export
    __uuid__: ClassVar[uuid4] = "35e4356e-b726-4c5b-b63f-620b301eb836"
    my_value: str


osl.register_schema(
    osl.SchemaRegistration(
        model_cls=MyClass, schema_name="MyClass", schema_bases=["Category:Item"]
    )
)

osl.fetch_schema(
    osl.FetchSchemaParam(
        schema_title="Category:" + OSL.get_osl_id(MyClass.__uuid__), mode="append"
    )
)
reload(model)

my_instance = model.MyClass(label=model.Label(text="My Instance"), my_value="test")
pprint(my_instance)
