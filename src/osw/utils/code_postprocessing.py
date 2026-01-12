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
