from pybars import Compiler


def eval_handlebars_template(
    template, data, helpers={}, partials={}, add_self_as_partial=True
):
    """evaluates a handlebars template with the given data

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
    compiler = Compiler()
    template = compiler.compile(template)
    if add_self_as_partial:
        partials["self"] = template
    return template(data, helpers=helpers, partials=partials)
