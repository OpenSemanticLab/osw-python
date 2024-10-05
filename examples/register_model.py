import os
from pprint import pprint
from typing import ClassVar
from uuid import uuid4

from pydantic.v1 import BaseModel

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


# todo: does dataclass export only most specific class jsonschema
class MyPythonClass(
    BaseModel
):  # We don't inherit from model.Item here because this will trigger a full schema
    #  export
    __uuid__: ClassVar[uuid4] = "23e4356e-b726-4c5b-b63f-620b301eb836"
    my_value: str


osw_obj.register_schema(
    osw_obj.SchemaRegistration(
        model_cls=MyPythonClass,
        schema_uuid=MyPythonClass.__uuid__,
        schema_name="MyPythonClass",
        schema_bases=["Category:Item"],
    )
)

osw_obj.fetch_schema(
    osw_obj.FetchSchemaParam(
        schema_title="Category:" + OSW.get_osw_id(MyPythonClass.__uuid__), mode="append"
    )
)

my_instance = model.MyPythonClass(
    label=[model.Label(text="My Instance")], my_value="test"
)
pprint(my_instance)
