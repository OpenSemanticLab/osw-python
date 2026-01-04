import re

from pybars import Compiler


def compile_handlebars_template(template):
    """compiles a handlebars template.
    WARNING: not thread safe!

    Parameters
    ----------
    template
        the template string

    Returns
    -------
        the compiled template
    """
    compiler = Compiler()
    # pybars does not support inline escaping, so we have to wrap the raw block
    # e.g. \{{escaped}} => {{{{raw}}}}{{escaped}}{{{{/raw}}}}
    # this workaround does not support expressions withing the escaped block,
    # e.g. \{{escaped {{some_var}} }} will not work
    # see https://handlebarsjs.com/guide/expressions.html#escaping-handlebars-expressions
    # see https://github.com/wbond/pybars3/pull/47
    template = re.sub(r"\\\{\{([^}]+)\}\}", r"{{{{raw}}}}{{\1}}{{{{/raw}}}}", template)
    compiled_template = compiler.compile(template)
    return compiled_template


# Python implementations of handlebars helpers
# https://github.com/OpenSemanticLab/mediawiki-extensions-MwJson/blob/main/modules/ext.MwJson.editor/MwJson_editor.js#L1342


def helper_join(this, options, context, separator=None, intro=None, outro=None):
    """
    removes all empty interation results and delimits them with
    the given separator (default: ", ")
    {{#join literal_array }}{{.}}{{/join}}
    {{#join object_array ", " "[" "]"}}{{#if print}}{{value}}{{/if}}{{/join}}
    """

    # handle optional params
    if intro is None:
        intro = ""
    if outro is None:
        outro = ""
    if separator is None:
        separator = ", "

    if context is None:
        context = []
    items = []

    for e in context:
        inner = "".join(options["fn"](e))
        items.append(inner)

    # Remove empty or whitespace-only elements
    items = [item for item in items if item.strip() != ""]
    if len(items) == 0:
        intro = outro = ""

    # Join with separator, wrap with intro + outro
    return intro + separator.join(items) + outro


def helper_replace(this, options, find, replace, flags=None):
    """
    Replace text in block content with plain string or regex

    Plain string replacement:
    {{#replace "old" "new"}}text{{/replace}}

    Regex replacement (with flags):
    {{#replace "(\\d{3})-(\\d{3})-(\\d{4})" "(\\1) \\2-\\3" "g"}}555-123-4567{{/replace}}

    Note: Use \\1, \\2 for capture groups in Python templates
    (or $1, $2 will be auto-converted from JavaScript style)
    """

    # Get the block content
    string = "".join(options["fn"](this))

    # If flags provided, use regex mode
    if flags:
        # Convert JavaScript flags to Python re flags
        re_flags = 0
        if "i" in flags:
            re_flags |= re.IGNORECASE
        if "m" in flags:
            re_flags |= re.MULTILINE
        if "s" in flags:
            re_flags |= re.DOTALL
        # Note: 'g' flag is implicit in Python's re.sub (replaces all by default)

        # Convert JavaScript-style backreferences ($1, $2) to Python style (\1, \2)
        replace_python = re.sub(r"\$(\d+)", r"\\\1", replace)
        replace_python = replace_python.replace("$&", r"\g<0>")  # Full match

        # Use re.sub
        result = re.sub(find, replace_python, string, flags=re_flags)
        return result

    # Default: plain string replacement (replace all occurrences)
    return string.replace(find, replace)


def eval_compiled_handlebars_template(
    compiled_template, data, helpers=None, partials=None, add_self_as_partial=True
):
    """evaluates a compiled handlebars template with the given data

    Parameters
    ----------
    compiled_template
        the compiled template
    data
        the data dictionary
    helpers
        helper functions, by default {}
    partials
        partials, by default {}
    add_self_as_partial
        if true, add the compiled template as partial 'self', by default True

    Returns
    -------
        the evaluated template as a string
    """

    default_helpers = {
        "join": helper_join,
        "replace": helper_replace,
    }
    if helpers is None:
        helpers = {}
    helpers = {**default_helpers, **helpers}

    if partials is None:
        partials = {}
    if add_self_as_partial:
        partials["self"] = compiled_template

    return compiled_template(data, helpers=helpers, partials=partials)


def eval_handlebars_template(
    template, data, helpers=None, partials=None, add_self_as_partial=True
):
    if helpers is None:
        helpers = {}
    if partials is None:
        partials = {}
    """evaluates a handlebars template with the given data.
    WARNING: not thread safe!

    Parameters
    ----------
    template
        the template string
    data
        the data dictionary
    helpers
        helper functions, by default {}
    partials
        partials, by default {}
    add_self_as_partial
        if true, add the compiled template as partial 'self', by default True

    Returns
    -------
        the evaluated template as a string
    """
    compiled_template = compile_handlebars_template(template)
    return eval_compiled_handlebars_template(
        compiled_template,
        data,
        helpers,
        partials,
        add_self_as_partial,
    )
