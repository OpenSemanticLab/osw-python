import re


def remove_constraints_from_forward_refs(src_code):
    """Remove min_items/max_items from Fields with forward reference types."""
    # First, identify all class definitions and their positions
    class_pattern = r"^class (\w+)\("
    classes = {}
    for match in re.finditer(class_pattern, src_code, re.MULTILINE):
        classes[match.group(1)] = match.start()

    # Pattern to match Field definitions with types
    pattern = r"(\w+):\s*list\[(\w+)\][^=]*=\s*Field\(((?:[^()]|\([^()]*\))*?)\)"

    def replace_field(match):
        field_name = match.group(1)
        type_name = match.group(2)
        field_args = match.group(3)
        field_start = match.start()

        # Check if type_name is a forward reference (defined later in the file)
        is_forward_ref = type_name in classes and classes[type_name] > field_start

        if is_forward_ref:
            if re.search(r"\bmin_items\s*=\s*\d+", field_args) or re.search(
                r"\bmax_items\s*=\s*\d+", field_args
            ):
                # Remove min_items and max_items
                new_args = re.sub(r",?\s*min_items\s*=\s*\d+", "", field_args)
                new_args = re.sub(r",?\s*max_items\s*=\s*\d+", "", new_args)

                # Clean up extra commas and whitespace
                new_args = re.sub(r",\s*,", ",", new_args)
                new_args = re.sub(r"^\s*,\s*", "", new_args)
                new_args = re.sub(r",\s*$", "", new_args)

                result = f"{field_name}: list[{type_name}] | None = Field({new_args})"
                # if min_items or max_items were in field args add comment:
                result += (
                    "\n# note: removed min_items/max_items due to forward reference"
                )
                return result

        return match.group(0)

    return re.sub(pattern, replace_field, src_code)


def resolve_osw_id_type_hints(content: str) -> str:
    """Replace bare OSW ID type hints with their actual class names.

    When datamodel-code-generator processes child schemas that override inherited
    properties with only options (e.g. {"options": {"hidden": true}}), it may use
    the JSON schema file stem (an OSW ID like OSW3886740859ae459588fee73d3bb3c83e)
    instead of the schema title (e.g. RiskAssessmentProcess) as the type name.

    This function builds a mapping from OSW IDs to class names by extracting UUIDs
    from class Config.schema_extra annotations in the generated code, then replaces
    any bare OSW ID references with the resolved class name.

    Parameters
    ----------
    content : str
        The generated Python source code (may contain multiple classes).

    Returns
    -------
    str
        The source code with bare OSW ID type hints replaced by class names.
    """
    # Build mapping: OSW ID -> class name from schema_extra uuid annotations
    # Each generated class has: class Foo(...): class Config: schema_extra = {"uuid": "..."}
    class_starts = list(re.finditer(r"^class\s+(\w+)\s*\(", content, re.MULTILINE))
    osw_id_to_class = {}
    for i, match in enumerate(class_starts):
        class_name = match.group(1)
        start = match.start()
        end = class_starts[i + 1].start() if i + 1 < len(class_starts) else len(content)
        class_block = content[start:end]
        uuid_match = re.search(
            r'"uuid":\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}'
            r"-[0-9a-f]{4}-[0-9a-f]{12})" + '"',
            class_block,
        )
        if uuid_match:
            osw_id = "OSW" + uuid_match.group(1).replace("-", "")
            osw_id_to_class[osw_id] = class_name

    if not osw_id_to_class:
        return content

    # Find bare OSW IDs used as identifiers (not inside "Category:OSW..." strings)
    bare_osw_pattern = re.compile(r"(?<![:\w])OSW[0-9a-f]{32}(?!\w)")
    unresolved = set(bare_osw_pattern.findall(content))

    for osw_id in unresolved:
        if osw_id in osw_id_to_class:
            content = re.sub(
                r"(?<![:\w])" + re.escape(osw_id) + r"(?!\w)",
                osw_id_to_class[osw_id],
                content,
            )

    return content
