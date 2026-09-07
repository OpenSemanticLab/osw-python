import re
from copy import deepcopy
from uuid import UUID

# Legacy imports:
from opensemantic.v1 import get_full_title, get_namespace, get_title  # noqa: F401

OSW_ID_PATTERN = re.compile(
    r"^(?:OSW)?"  # the prefix, absent when a bare uuid is passed
    r"([0-9a-fA-F]{32})"  # the uuid, in the hex form an OSW-ID carries it
    r"(?:\.[\w-]+)*$"  # file suffixes, e.g. '.png' or '.drawio.png'
)
"""Matches an OSW-ID with an optional prefix and any number of file suffixes"""


def get_osw_id(uuid: UUID) -> str:
    """Generates a OSW-ID based on the given uuid by prefixing "OSW" and removing
    all '-' from the uuid-string. Duplicates OSW.get_osw_id() from src/sw/core/osw.py

    Parameters
    ----------
    uuid
        An UUID object, e.g., UUID("2ea5b605-c91f-4e5a-9559-3dff79fdd4a5")

    Returns
    -------
        OSW-ID string, e.g., OSW2ea5b605c91f4e5a95593dff79fdd4a5
    """
    return "OSW" + str(uuid).replace("-", "")


def get_uuid(osw_id: str) -> UUID:
    """Returns the uuid for a given OSW-ID. The single implementation, wrapped by
    OSW.get_uuid() from src/osw/core.py

    A file page keeps its file extension in the title, so the OSW-ID of a file is
    followed by one or more suffixes that are not part of the uuid. These are
    ignored, as is the OSW prefix.

    Parameters
    ----------
    osw_id
        OSW-ID string, e.g., OSW2ea5b605c91f4e5a95593dff79fdd4a5, with or without
        file suffixes, e.g., OSW2ea5b605c91f4e5a95593dff79fdd4a5.drawio.png

    Returns
    -------
        uuid object, e.g., UUID("2ea5b605-c91f-4e5a-9559-3dff79fdd4a5")

    Raises
    ------
    ValueError
        If no OSW-ID can be read from the given string.
    """
    match = OSW_ID_PATTERN.match(osw_id)
    if match is None:
        raise ValueError(f"No OSW-ID could be read from '{osw_id}'")
    return UUID(match.group(1))


def namespace_from_full_title(full_title: str) -> str:
    """extracts the namespace from a full title (namespace:title)

    Parameters
    ----------
    full_title
        the full title to extract the namespace from

    Returns
    -------
        the namespace as a string
    """
    return full_title.replace(title_from_full_title(full_title), "").replace(":", "")


def title_from_full_title(full_title: str) -> str:
    """extracts the title from a full title (namespace:title)

    Parameters
    ----------
    full_title
        the full title to extract the title from

    Returns
    -------
        the title as a string
    """
    namespace = full_title.split(":")[0]
    return full_title.split(f"{namespace}:")[-1]


def is_empty(val):
    """checks if the given value is empty"""
    if val is None:
        return True
    elif isinstance(val, list) or isinstance(val, str) or isinstance(val, dict):
        return len(val) == 0
    return False


def remove_empty_strings(d: dict, inplace: bool = True) -> dict:
    """Iterates through the dictionary structure and removes key-value pairs
    where the value is an empty string

    Parameters
    ----------
    d:
        The dictionary to perform the operation on
    inplace:
        Whether to perform the operation in place or return a new dictionary

    Returns
    -------
    result:
        The modified dictionary
    """
    if not inplace:
        d = deepcopy(d)
    keys = list(d.keys())
    for key in keys:
        value = d[key]
        if isinstance(value, dict):
            remove_empty_strings(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    remove_empty_strings(item)
        if value == "":
            del d[key]
    return d


def remove_empty(d: dict, inplace: bool = True) -> dict:
    """Iterates through the dictionary structure and removes key-value pairs
    where the value is an empty string, list, set or dictionary

    Parameters
    ----------
    d:
        The dictionary to perform the operation on
    inplace:
        Whether to perform the operation in place or return a new dictionary

    Returns
    -------
    result:
        The modified dictionary
    """
    if d is None:
        return d
    if not inplace:
        d = deepcopy(d)
    keys = list(d.keys())
    for key in keys:
        value = d[key]
        if isinstance(value, dict):
            remove_empty(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    remove_empty(item)
        if value in ["", [], {}, set()]:
            del d[key]
    return d
