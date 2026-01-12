import re

from osw.utils.code_postprocessing import remove_constraints_from_forward_refs


def test_remove_constraints_from_forward_refs():
    """Test that min_items/max_items are removed only from forward references."""

    src_code = '''class Distribution(OswBaseModel):
    class Config:
        schema_extra = {"title": "Distribution"}

    download_url: str = Field(..., title="Download URL")


class DatasetSchema(Item):
    class Config:
        schema_extra = {
            "@context": [{"schema_definition": "Property:HasSchemaDefinition"}],
            "title": "DatasetSchema",
            "defaultProperties": ["schema_definition", "label", "uuid"],
        }

    schema_definition: str | None = Field(None, title="Dataset schema")
    """
    Defintion of a JSON based Schema for a dataset.
    """
    type: list[str] | None = ["Category:OSW0d6584b3e2b64e9595733c4c3963c486"]


class Dataset(Data):
    class Config:
        schema_extra = {
            "@context": [
                "/wiki/Category:OSW2ac4493f8635481eaf1db961b63c8325?action=raw&slot=jsonschema",
                {
                    "url": "dcat:landingPage",
                    "url*": "Property:HasUrl",
                    "themes": {"@type": "@id", "@id": "dcat:theme"},
                    "themes*": {"@type": "@id", "@id": "Property:IsRelatedTo"},
                    "distributions": {"@type": "@id", "@id": "dcat:distribution"},
                    "distributions*": {
                        "@type": "@id",
                        "@id": "Property:HasDistribution",
                    },
                    "download_url": "dcat:downloadURL",
                    "download_url*": "Property:HasUrl",
                    "data_format": "Property:HasDataFormat",
                    "dataset_schema": "Property:HasDatasetSchema",
                },
            ],
            "title": "Dataset",
            "defaultProperties": ["url", "themes"],
            "uuid": "fe729745-90fd-4e8b-a94c-d4e8366375e8",
            "title*": {"en": "Dataset"},
            "description": "",
            "description*": {},
        }

    type: list[str] | None = ["Category:OSWfe72974590fd4e8ba94cd4e8366375e8"]
    url: list[str] | None = Field(None, title="URL / Websites")
    """
    Landing page(s) that documents the dataset
    """
    themes: list[Entity] | None = Field(
        None, range="Category:Entity", title="Themes / Topics"
    )
    """
    Terms to categorizes this dataset
    """
    distributions: list[Distribution] | None = Field(
        None, title="Distributions / Downloads"
    )
    """
    Actual download options for this dataset
    """
    data_format: list[DataFormat] | None = Field(
        None,
        min_items=1,
        range="Category:OSWccac243b31f94574847861e5d9685b82",
        title="Data format",
    )
    data_f: list[DataFormat] | None = Field(None, min_items=1, title="Test")
    """
    Gives a structure to define specific formats of data.
    """
    dataset_schema: list[DatasetSchema] | None = Field(
        None,
        min_items=1,
        range="Category:OSW0d6584b3e2b64e9595733c4c3963c486",
        title="Dataset schema",
    )


class DataTerm(DefinedTerm):
    class Config:
        schema_extra = {
            "@context": [
                "/wiki/Category:OSWa5812d3b5119416c8da1606cbe7054eb?action=raw&slot=jsonschema"
            ],
            "title": "DataTerm",
        }

    type: list[str] | None = ["Category:OSW34f9d66c7e1241c8b9543231526f126d"]


class DataFormat(DataTerm):
    class Config:
        schema_extra = {
            "defaultProperties": [
                "specification",
                "description",
                "label",
                "short_name",
            ],
            "title": "DataFormat",
        }

    specification: str | None = Field(
        None,
        description_={"de": "Entweder Text oder Link"},
        title="Specification",
        title_={"de": "Spezifikation"},
    )
    """
    Either text or link
    """
    type: list[str] | None = ["Category:OSWccac243b31f94574847861e5d9685b82"]
'''  # noqa

    result = remove_constraints_from_forward_refs(src_code)

    # Test 1: DataFormat forward references should have min_items removed
    assert (
        "data_format: list[DataFormat] | None = Field(\n        None,\n        min_items=1,"  # noqa
        not in result
    )
    assert (
        "data_format: list[DataFormat] | None = Field(\n        None,\n        range="
        in result
    )

    # Test 2: data_f field should have min_items removed
    assert (
        'data_f: list[DataFormat] | None = Field(None, min_items=1, title="Test")'
        not in result
    )
    assert 'data_f: list[DataFormat] | None = Field(None, title="Test")' in result

    # Test 3: DatasetSchema is NOT a forward ref (defined before Dataset),
    # so min_items should remain
    assert (
        "dataset_schema: list[DatasetSchema] | None = Field(\n        None,\n        min_items=1,"  # noqa
        in result
    )

    # Test 4: Other fields should remain unchanged
    assert (
        'distributions: list[Distribution] | None = Field(\n        None, title="Distributions / Downloads"\n    )'  # noqa
        in result
    )
    assert (
        'themes: list[Entity] | None = Field(\n        None, range="Category:Entity", title="Themes / Topics"\n    )'  # noqa
        in result
    )

    # Test 5: Class definitions should remain unchanged
    assert "class Distribution(OswBaseModel):" in result
    assert "class DatasetSchema(Item):" in result
    assert "class Dataset(Data):" in result
    assert "class DataFormat(DataTerm):" in result

    print("All tests passed!")


def test_edge_cases():
    """Test edge cases for the regex function."""

    # Test case 1: max_items should also be removed
    src_code_with_max = """class Dataset(Data):
    data_format: list[DataFormat] | None = Field(None, min_items=1, max_items=10, title="Data format")  # noqa

class DataFormat(DataTerm):
    pass
"""
    result = remove_constraints_from_forward_refs(src_code_with_max)
    assert "min_items=1" not in result
    assert "max_items=10" not in result
    assert 'title="Data format"' in result

    # Test case 2: No forward references - should not remove constraints
    src_code_no_forward = """class DataFormat(DataTerm):
    pass

class Dataset(Data):
    data_format: list[DataFormat] | None = Field(None, min_items=1, title="Data format")
"""
    result = remove_constraints_from_forward_refs(src_code_no_forward)
    assert "min_items=1" in result  # Still forward ref since DataFormat is before

    # Test case 3: Multiple constraints on same line
    src_code_multiple = """class Dataset(Data):
    field1: list[ForwardType] | None = Field(None, min_items=1, max_items=5, range="test")
    field2: list[BackwardType] | None = Field(None, min_items=2, title="Test")

class BackwardType(Item):
    pass

class ForwardType(Item):
    pass
"""
    result = remove_constraints_from_forward_refs(src_code_multiple)
    # field1 references ForwardType (defined later) - constraints should be removed
    assert "field1: list[ForwardType]" in result
    assert re.search(r"field1:.*min_items=1", result) is None
    assert re.search(r"field1:.*max_items=5", result) is None
    # field2 references BackwardType (defined later) - constraints should be removed
    assert re.search(r"field2:.*min_items=2", result) is None

    print("All edge case tests passed!")


if __name__ == "__main__":
    test_remove_constraints_from_forward_refs()
    test_edge_cases()
