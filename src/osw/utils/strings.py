# Functions


def camel_case(st: str) -> str:
    """converts a string to camelCase

    Parameters
    ----------
    st
        the string to convert to camelCase

    Returns
    -------
        The string in camelCase
    """
    if not st.isalnum():
        st = "".join(x for x in st.title() if x.isalnum())
    return st[0].lower() + st[1:]


def pascal_case(st: str) -> str:
    """converts a string to PascalCase

    Parameters
    ----------
    st
        the string to convert to PascalCase

    Returns
    -------
        The string in PascalCase
    """
    if not st.isalnum():
        st = "".join(x for x in st.title() if x.isalnum())
    return st[0].upper() + st[1:]
