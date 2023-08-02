from typing import Union

import osw.model.entity as model


def get_namespace(entity: model.Entity) -> Union[str, None]:
    """determines the wiki namespace based on the entity's type/class

    parameters:
        entity: the entity to determine the namespace for

    returns:
        the namespace as a string or None if the namespace could not be determined
    """
    namespace = None
    #  (model classes may not exist => try except)
    if namespace is None:
        try:
            if issubclass(entity, model.Entity):
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
            if isinstance(entity, model.Category):
                namespace = "Category"
        except AttributeError:
            pass
    if namespace is None:
        try:
            if isinstance(entity, model.Property):
                namespace = "Property"
        except AttributeError:
            pass
    if namespace is None:
        try:
            if isinstance(entity, model.WikiFile):
                namespace = "File"
        except AttributeError:
            pass

    return namespace
