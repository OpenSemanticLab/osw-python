"""Contains essential functions for working with JSON, JSON-SCHEMA
and JSON-LD context objects. Python implementation of
https://github.com/OpenSemanticLab/mediawiki-extensions-MwJson/blob/main/modules/ext.MwJson.util/MwJson_util.js
"""

import json
from copy import deepcopy
from enum import Enum
from typing import Dict, Optional, TypeVar

from pydantic import BaseModel
from typing_extensions import deprecated

JsonType = TypeVar("JsonType", dict, list, float, int, str, None)


def deep_equal(x: JsonType, y: JsonType):
    """Compares two objects deeply.

    Parameters
    ----------
    x
        a dictionary, list or scalar value
    y
        another dictionary, list or scalar value

    Returns
    -------
        True if the two objects are deeply equal, False otherwise
    """

    if x is not None and y is not None and isinstance(x, dict) and isinstance(y, dict):
        return len(x.keys()) == len(y.keys()) and all(
            deep_equal(x[key], y.get(key, None)) for key in x
        )
    elif (
        x is not None and y is not None and isinstance(x, list) and isinstance(y, list)
    ):
        return len(x) == len(y) and all(
            deep_equal(x[key], y[key]) for key in range(0, len(x))
        )
    else:
        return x == y
    # all(deep_equal(x[key], y.get(key)) for key in x) or x == y


def unique_array(array: list) -> list:
    """Returns a new array with only unique elements by comparing them deeply.

    Parameters:
    array: list
        The array to be filtered

    Returns:
    list
        A new array with only unique elements
    """
    result = []
    for item in array:
        add = True
        for added_item in result:
            if deep_equal(added_item, item):
                add = False
                break
        if add:
            result.append(item)
    return result


def is_object(obj):
    """Tests if an object is a dictionary.

    Parameters
    ----------
    obj
        the object to be tested

    Returns
    -------
        True if the object is a dictionary, False otherwise
    """
    return isinstance(obj, dict)


def is_array(obj):
    """Tests if an object is a list.

    Parameters
    ----------
    obj
        the object to be tested

    Returns
    -------
        True if the object is a list, False otherwise
    """
    return isinstance(obj, list)


def is_string(obj):
    """Tests if an object is a string.

    Parameters
    ----------
    obj
        the object to be tested

    Returns
    -------
        True if the object is a string, False otherwise
    """
    return isinstance(obj, str)


def copy_deep(target: JsonType) -> JsonType:
    """Copies an object deeply.

    Parameters
    ----------
    target
        the object which values will be copied

    Returns
    -------
        the copied object
    """
    return deepcopy(target)


@deprecated("Use merge_deep instead")
def merge_deep_objects(target: dict, source: dict) -> JsonType:
    """Merges two objects deeply, does not handle lists.
    If dictionaries are encountered, the values of the source object
    will overwrite the target object.
    Missing keys in the target object will be added.
    If an array is encountered as a subelement, the arrays are
    concatenated and duplicates are removed.
    If literals are encountered, the source value will
    overwrite the target value.

    Parameters
    ----------
    target
        the object which values will be potentially overwritten
    source
        the object which values will take precedence over the target object

    Returns
    -------
        the merged object
    """
    if not target:
        return source
    if not source:
        return target
    output = deepcopy(target)
    if is_object(target) and is_object(source):
        for key in source:
            if is_array(source[key]) and is_array(target.get(key)):
                if key not in target:
                    output[key] = source[key]
                else:
                    output[key] = unique_array(target[key] + source[key])
            elif is_object(source[key]):
                if key not in target:
                    output[key] = source[key]
                else:
                    output[key] = merge_deep(target[key], source[key])
            else:
                output[key] = source[key]

    return output


def merge_deep(target: JsonType, source: JsonType) -> JsonType:
    """Merges two objects deeply.
    If dictionaries are encountered, the values of the source object
    will overwrite the target object.
    Missing keys in the target object will be added.
    If an array is encountered as a subelement, the arrays are
    concatenated and duplicates are removed.
    If literals are encountered, the source value will
    overwrite the target value.

    Parameters
    ----------
    target
        the object which values will be potentially overwritten
    source
        the object which values will take precedence over the target object

    Returns
    -------
        the merged object
    """
    if not target:
        return source
    if not source:
        return target
    output = deepcopy(target)

    if is_object(target) and is_object(source):
        for key in source:
            output[key] = merge_deep(output.get(key, None), source[key])
    elif is_array(source) and is_array(target):
        output = unique_array(target + source)
    else:
        output = source
    return output


def merge_jsonld_context_object_list(context: list) -> list:
    """to cleanup generated json-ld context
    ["/some/remove/context", {"a": "ex:a"}, {"a": "ex:a", "b": "ex:b"}]
        => ["/some/remove/context", {"a": "ex:a", "b": "ex:b"}]

    Parameters
    ----------
    list
        mixed list of strings and dictionaries
    """

    # interate over all elements
    # if element is a string, add it to the result list
    # if element is a dictionary, merge it with the last dictionary in the
    # result list

    # if not a list, return immediately
    if not is_array(context):
        return context

    result = []
    last = None
    for e in context:
        if is_object(e):
            if last is None:
                last = e
            else:
                last = merge_deep(last, e)
        else:
            if last is not None:
                result.append(last)
                last = None
            result.append(e)
    if last is not None:
        result.append(last)
    return result


class AggregateGeneratedSchemasParamMode(str, Enum):
    ROOT_LEVEL = "root_level"
    """ The generated schema is merged at the root level """
    DEFINITIONS_SECTION = "definitions_section"
    """ The generated schema is merged into the definitions section """


class AggregateGeneratedSchemasParam(BaseModel):
    target_schema: Optional[dict] = {}
    """ The target schema to be merged with the generated schema """
    generated_schemas: Dict[str, dict]
    """ List of JSON schemas to be aggregated """
    mode: AggregateGeneratedSchemasParamMode = (
        AggregateGeneratedSchemasParamMode.ROOT_LEVEL
    )
    """ The mode to be used for aggregation """
    def_key: Optional[str] = "$defs"
    """ The keyword for schema definitions. $defs is recommended"""
    gen_def_key: Optional[str] = "generated"
    """ The keyword to store the generated schema.
    Note: Having a separate section per generated schema would lead
    to many partial classes in code generation """
    generate_root_ref: Optional[bool] = False
    """ If true, generate $ref: "#/def...", else allOf: [{$ref: "#/def...""}.
    Root refs are not supported by json_ref_parser < 0.10 and data-model-codegen """
    gen_def_pointer: Optional[str] = None
    """ The pointer to the generated schema. If None, it will be set to
    "#/" + def_key + "/" + gen_def_key """

    def __init__(self, **data):
        super().__init__(**data)
        if self.gen_def_pointer is None:
            self.gen_def_pointer = "#/" + self.def_key + "/" + self.gen_def_key


class AggregateGeneratedSchemasResult(BaseModel):
    aggregated_schema: dict
    """ The aggregated schema """


def aggregate_generated_schemas(
    param: AggregateGeneratedSchemasParam,
) -> AggregateGeneratedSchemasResult:
    """Applies a merge operation on two OO-LD schemas.

    Parameters
    ----------
    param
        see AggregateGeneratedSchemasParam

    Returns
    -------
        see AggregateGeneratedSchemasResult
    """
    mode = param.mode
    def_key = param.def_key
    gen_def_key = param.gen_def_key
    gen_def_pointer = param.gen_def_pointer
    generate_root_ref = param.generate_root_ref
    schema = param.target_schema

    for generated_schema_id in param.generated_schemas.keys():
        generated_schema = param.generated_schemas[generated_schema_id]
        if mode == AggregateGeneratedSchemasParamMode.ROOT_LEVEL:
            schema = merge_deep(schema, generated_schema)
        else:
            # Store generated schema in #/$defs/generated (force overwrite),
            # add $ref: #/$defs/generated to schema
            # note: using $def with $ leads to recursion error in
            # note: requires addition schema properties are allowed on the
            # same level as $ref. allOf: $ref would imply a superclass
            if "@context" in generated_schema:
                generated_context = copy_deep(generated_schema["@context"])
                del generated_schema["@context"]
                existing_context = schema.get("@context", None)
                if existing_context is not None:
                    # case A: "" + "" => ["", ""]
                    # case B: "" + {} => ["", {}]
                    # case C: "" + [] => ["", ]
                    # case D: [] + {} => [, {}]
                    # case E: {} + {} => {}
                    # case F: [] + [] => []

                    if is_array(existing_context) and not is_array(generated_context):
                        generated_context = [generated_context]
                        # case C + D
                    elif not is_array(existing_context) and is_array(generated_context):
                        existing_context = [existing_context]
                        # case C + D
                    elif not is_array(existing_context) and not is_array(
                        generated_context
                    ):
                        if is_string(existing_context) or is_string(
                            existing_context
                        ):  # case A + B
                            generated_context = [generated_context]
                            existing_context = [existing_context]
                    # case E + F: nothing to do
                schema["@context"] = merge_deep(
                    {"@context": existing_context}, {"@context": generated_context}
                )["@context"]
                if is_array(schema["@context"]):
                    schema["@context"] = merge_jsonld_context_object_list(
                        schema["@context"]
                    )

            if def_key not in schema:
                schema[def_key] = {}
            if gen_def_key not in schema[def_key]:
                schema[def_key][gen_def_key] = {
                    "$comment": "Autogenerated section - do not edit. Generated from"
                }
            schema[def_key][gen_def_key]["$comment"] += " " + generated_schema_id
            # schema[def_key][gen_def_key] = generated_schema; # full override
            schema[def_key][gen_def_key] = merge_deep(
                schema[def_key][gen_def_key], generated_schema
            )
            # merge

            if generate_root_ref:
                if "$ref" in schema and schema["$ref"] != gen_def_pointer:
                    print(
                        "Error while applying generated schema: $ref already set to "
                        + schema["$ref"]
                    )
                else:
                    schema["$ref"] = gen_def_pointer
            else:
                if "allOf" not in schema:
                    schema["allOf"] = []
                # check if any allOf already points to the generated schema
                exists = any(
                    [allOf["$ref"] == gen_def_pointer for allOf in schema["allOf"]]
                )
                if not exists:
                    schema["allOf"].append({"$ref": gen_def_pointer})
                if "title" in generated_schema:
                    schema["title"] = generated_schema["title"]
                    schema[def_key][gen_def_key]["title"] = (
                        "Generated" + generated_schema["title"]
                    )
                    schema[def_key][gen_def_key]["description"] = (
                        "This is an autogenerated partial class definition of '"
                        + generated_schema["title"]
                        + "'"
                    )
                if "description" in generated_schema:
                    schema["description"] = generated_schema["description"]

    return AggregateGeneratedSchemasResult(aggregated_schema=schema)


def escape_json_strings(obj: JsonType) -> JsonType:
    """replace double quotes `"` with escaped double quotes `\"` in
    and non-standard escape-squences in strings.
    If the object is a string, the escaped string is returned.
    If the object is a list, the function is called recursively for each element.
    If the object is a dictionary, the function is called recursively for each value.
    Else the object is returned as is.

    Parameters
    ----------
    obj
        the object to handle

    Returns
    -------
        returns the object with double quotes escaped if applicable
    """
    if isinstance(obj, str):
        # Escape double quotes in string
        # Replace invalid backslashes outside of math environments
        return json.dumps(obj)[1:-1]
    elif isinstance(obj, list):
        # Iterate over array elements
        return [escape_json_strings(item) for item in obj]
    elif isinstance(obj, dict):
        # Iterate over object properties
        escaped_obj = {}
        for key, value in obj.items():
            escaped_obj[key] = escape_json_strings(value)
        return escaped_obj
    # Return the value as is for non-string, non-object types
    return obj
