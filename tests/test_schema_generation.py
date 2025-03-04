import json
from typing import Optional

import jsondiff
from pydantic.v1 import BaseModel, Field

import osw.model.entity as model
from osw.utils.wiki import get_osw_id


class SubObject(BaseModel):
    prop1: int
    prop2: int


class MyCustomSchema(model.Item):
    class Config:
        schema_extra = {
            "@context": [
                {"my_property": "https://example.org/my_property"},
            ],
        }

    a_simple_property: int
    """
    A simple test
    """
    my_property: Optional[str] = Field(
        "default value",
        title="My property",
        title_={"de": "Mein Attribut"},
        description="A test property",
        description_={"de": "Dies ist ein Test-Attribut"},
    )

    a_object_property: SubObject


def test_schema_generation():
    baseclass_schema = {}
    imports = []

    toplevel_classes = {"Entity": "Entity", "Item": "Item"}

    for baseclass in MyCustomSchema.__bases__:
        baseclass: BaseModel = baseclass
        schema = json.loads(
            baseclass.schema_json(ref_template="#/$defs/{model}", indent=2).replace(
                "$$ref", "$ref"
            )
        )
        baseclass_oswid = ""
        if baseclass.__name__ in toplevel_classes:
            baseclass_oswid = toplevel_classes[baseclass.__name__]
        else:
            baseclass_oswid = get_osw_id(baseclass.__config__.schema_extra["uuid"])

        imports.append(f"/wiki/Category:{baseclass_oswid}?action=raw&slot=jsonschema")
        # ToDO: Use deepmerge
        baseclass_schema = {**baseclass_schema, **schema}

    my_schema_full = json.loads(
        MyCustomSchema.schema_json(ref_template="#/$defs/{model}", indent=2).replace(
            "$$ref", "$ref"
        )
    )

    # print(MyCustomSchema.schema_json(indent=2))
    my_schema_diff = jsondiff.diff(baseclass_schema, my_schema_full, marshal=True)
    context = my_schema_diff.pop("@context")

    if not isinstance(context, list):
        context = [context]
    missing_imports = []
    for imp in imports:
        if imp not in context:
            missing_imports.append(imp)
    context = [*missing_imports, *context]
    required = []
    if "required" in my_schema_diff:
        for r in my_schema_diff["required"]["$insert"]:
            required.append(r[1])
        del my_schema_diff["required"]
    if "$delete" in my_schema_diff:
        del my_schema_diff["$delete"]
    defs = {}
    if "definitions" in my_schema_diff:
        defs = my_schema_diff.pop("definitions")
    if "$defs" in my_schema_diff:
        defs = {**defs, **my_schema_diff.pop("$defs")}
    my_schema = {
        "@context": context,
        "$defs": defs,
        "required": required,
        **json.loads(
            json.dumps(my_schema_diff)
            .replace("title_", "title*")
            .replace("description_", "description*")
            .replace("$$ref", "$ref")
        ),
    }
    print(json.dumps(my_schema, indent=2))

    assert my_schema == {
        "@context": [
            "/wiki/Category:Item?action=raw&slot=jsonschema",
            {"my_property": "https://example.org/my_property"},
        ],
        "$defs": {
            "SubObject": {
                "title": "SubObject",
                "type": "object",
                "properties": {
                    "prop1": {"title": "Prop1", "type": "integer"},
                    "prop2": {"title": "Prop2", "type": "integer"},
                },
                "required": ["prop1", "prop2"],
            }
        },
        "required": ["a_simple_property", "a_object_property"],
        "title": "MyCustomSchema",
        "properties": {
            "a_simple_property": {"title": "A Simple Property", "type": "integer"},
            "my_property": {
                "title": "My property",
                "description": "A test property",
                "default": "default value",
                "title*": {"de": "Mein Attribut"},
                "description*": {"de": "Dies ist ein Test-Attribut"},
                "type": "string",
            },
            "a_object_property": {"$ref": "#/$defs/SubObject"},
        },
    }


# test_schema_generation()
