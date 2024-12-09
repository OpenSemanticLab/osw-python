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
    helpers, optional
        helper functions, by default {}
    partials, optional
        partials, by default {}
    add_self_as_partial, optional
        if true, add the compiled template as partial 'self', by default True

    Returns
    -------
        the evaluated template as a string
    """

    default_helpers = {
        "join": helper_join,
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
    helpers, optional
        helper functions, by default {}
    partials, optional
        partials, by default {}
    add_self_as_partial, optional
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
