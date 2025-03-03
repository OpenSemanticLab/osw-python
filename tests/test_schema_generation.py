import json
from typing import Optional

import jsondiff
from pydantic.v1 import Field

import osw.model.entity as model


class MyCustomSchema(model.Entity):
    class Config:
        schema_extra = {
            "@context": [
                "/wiki/Category:Entity?action=raw&slot=jsonschema",
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


def test_schema_generation():
    entity_schema = json.loads(model.Entity.schema_json(indent=2))
    my_schema_full = json.loads(MyCustomSchema.schema_json(indent=2))

    # print(MyCustomSchema.schema_json(indent=2))
    my_schema_diff = jsondiff.diff(entity_schema, my_schema_full, marshal=True)
    context = my_schema_diff.pop("@context")
    required = []
    if "required" in my_schema_diff:
        for r in my_schema_diff["required"]["$insert"]:
            required.append(r[1])
        del my_schema_diff["required"]
    del my_schema_diff["$delete"]
    my_schema = {
        "@context": context,
        "required": required,
        **json.loads(
            json.dumps(my_schema_diff)
            .replace("title_", "title*")
            .replace("description_", "description*")
        ),
    }
    print(json.dumps(my_schema, indent=2))

    assert my_schema == {
        "@context": [
            "/wiki/Category:Entity?action=raw&slot=jsonschema",
            {"my_property": "https://example.org/my_property"},
        ],
        "required": ["a_simple_property"],
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
        },
    }
