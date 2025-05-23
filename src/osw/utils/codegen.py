from pathlib import Path
from typing import Any, Dict

from datamodel_code_generator import load_yaml_from_path
from datamodel_code_generator.model import pydantic as pydantic_v1_model
from datamodel_code_generator.model import pydantic_v2 as pydantic_v2_model
from datamodel_code_generator.parser.jsonschema import (
    JsonSchemaObject,
    JsonSchemaParser,
)

# https://docs.pydantic.dev/1.10/usage/schema/#schema-customization
# https://docs.pydantic.dev/latest/concepts/json_schema/#using-json_schema_extra-with-a-dict
# https://docs.pydantic.dev/latest/concepts/json_schema/#field-level-customization


class PydanticV1Config(pydantic_v1_model.Config):
    # schema_extra: Optional[Dict[str, Any]] = None
    schema_extra: str = None


class PydanticV2Config(pydantic_v2_model.ConfigDict):
    # schema_extra: Optional[Dict[str, Any]] = None
    json_schema_extra: str = None


class OOLDJsonSchemaParser(JsonSchemaParser):
    """Custom parser for OO-LD schemas.
    You can use this class directly or monkey-patch the datamodel_code_generator module:
    `datamodel_code_generator.parser.jsonschema.JsonSchemaParser = OOLDJsonSchemaParser`
    """

    def set_additional_properties(self, name: str, obj: JsonSchemaObject) -> None:
        schema_extras = repr(obj.extras)  # keeps 'False' and 'True' boolean literals
        if self.data_model_type == pydantic_v1_model.BaseModel:
            self.extra_template_data[name]["config"] = PydanticV1Config(
                schema_extra=schema_extras
            )
        if self.data_model_type == pydantic_v2_model.BaseModel:
            self.extra_template_data[name]["config"] = PydanticV2Config(
                json_schema_extra=schema_extras
            )
        return super().set_additional_properties(name, obj)


class OOLDJsonSchemaParserFixedRefs(OOLDJsonSchemaParser):
    """Overwrite # overwrite the original `_get_ref_body_from_remote` function
    to fix wrongly composed paths. This issue occurs only when using this parser class directy
    and occurs not if used through mokey patching and `datamodel_code_generator.generate()`
    """

    def _get_ref_body_from_remote(self, resolved_ref: str) -> Dict[Any, Any]:
        # full_path = self.base_path / resolved_ref
        # fix: merge the paths correctly
        full_path = self.base_path / Path(resolved_ref).parts[-1]
        return self.remote_object_cache.get_or_put(
            str(full_path),
            default_factory=lambda _: load_yaml_from_path(full_path, self.encoding),
        )
