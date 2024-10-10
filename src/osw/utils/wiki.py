from typing import Type, Union
from uuid import UUID

import osw.model.entity as model
from osw.model.static import OswBaseModel


def get_osw_id(uuid: UUID) -> str:
    """Generates a OSW-ID based on the given uuid by prefixing "OSW" and removing
    all '-' from the uuid-string. Duplicates OSW.get_osw_id() from src/sw/core/osw.py

    Parameters
    ----------
    uuid
        uuid object, e. g. UUID("2ea5b605-c91f-4e5a-9559-3dff79fdd4a5")

    Returns
    -------
        OSW-ID string, e. g. OSW2ea5b605c91f4e5a95593dff79fdd4a5
    """
    return "OSW" + str(uuid).replace("-", "")


def get_uuid(osw_id) -> UUID:
    """Returns the uuid for a given OSW-ID. Duplicate of OSW.get_uuid() from src/sw/core/osw.py

    Parameters
    ----------
    osw_id
        OSW-ID string, e. g. OSW2ea5b605c91f4e5a95593dff79fdd4a5

    Returns
    -------
        uuid object, e. g. UUID("2ea5b605-c91f-4e5a-9559-3dff79fdd4a5")
    """
    return UUID(osw_id.replace("OSW", ""))


def get_namespace(entity: Union[OswBaseModel, Type[OswBaseModel]]) -> Union[str, None]:
    """determines the wiki namespace based on the entity's type/class

    Parameters
    ----------
    entity
        the entity to determine the namespace for

    Returns
    -------
        the namespace as a string or None if the namespace could not be determined
    """
    namespace = None

    if hasattr(entity, "meta") and entity.meta and entity.meta.wiki_page:
        if entity.meta.wiki_page.namespace:
            namespace = entity.meta.wiki_page.namespace

    #  (model classes may not exist => try except)
    #  note: this may not work properly with dynamic reloaded model module
    #  note: some of these lines lead to AssertationError in coverage.py
    #        and are therefore excluded from coverage
    #        (see also https://github.com/OpenSemanticLab/osw-python/issues/74)
    if namespace is None:
        try:
            if issubclass(entity, model.Entity):
                namespace = "Category"
        except (TypeError, AttributeError):
            pass
    if namespace is None:
        try:
            if isinstance(entity, model.Category):  # pragma: no cover
                namespace = "Category"
        except AttributeError:
            pass
    if namespace is None:
        try:
            if issubclass(entity, model.Characteristic):  # pragma: no cover
                namespace = "Category"
        except (TypeError, AttributeError):
            pass
    if namespace is None:
        try:
            if isinstance(entity, model.Item):
                namespace = "Item"
        except AttributeError:
            pass
    if namespace is None:
        try:
            if isinstance(entity, model.Property):  # pragma: no cover
                namespace = "Property"
        except AttributeError:
            pass
    if namespace is None:
        try:
            if isinstance(entity, model.WikiFile):  # pragma: no cover
                namespace = "File"
        except AttributeError:
            pass

    return namespace


def get_title(entity: model.Entity) -> Union[str, None]:
    """determines the wiki page title based on the entity's data

    Parameters
    ----------
    entity
        the entity to determine the title for

    Returns
    -------
        the title as a string or None if the title could not be determined
    """
    title = None

    if hasattr(entity, "meta") and entity.meta and entity.meta.wiki_page:
        if entity.meta.wiki_page.title:
            title = entity.meta.wiki_page.title

    if title is None:
        title = get_osw_id(entity.uuid)

    return title


def get_full_title(entity: model.Entity) -> Union[str, None]:
    """determines the wiki full title (namespace:title) based on the entity's data

    Parameters
    ----------
    entity
        the entity to determine the full title for

    Returns
    -------
        the full title as a string or None if the title could not be determined
    """
    namespace = get_namespace(entity)
    title = get_title(entity)
    if namespace is not None and title is not None:
        return namespace + ":" + title
    else:
        return title


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
    return full_title.split(":")[-1]


def is_empty(val):
    """checks if the given value is empty"""
    if val is None:
        return True
    elif isinstance(val, list) or isinstance(val, str) or isinstance(val, dict):
        return len(val) == 0
    return False
