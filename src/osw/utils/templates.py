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
    template = compiler.compile(template)
    return template


def eval_compiled_handlebars_template(
    compiled_template, data, helpers={}, partials={}, add_self_as_partial=True
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
    if add_self_as_partial:
        partials["self"] = compiled_template
    return compiled_template(data, helpers=helpers, partials=partials)


def eval_handlebars_template(
    template, data, helpers={}, partials={}, add_self_as_partial=True
):
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
