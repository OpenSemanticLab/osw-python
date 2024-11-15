"""
This module is to be imported in the dynamically created and updated entity.py module.
"""

from typing import TYPE_CHECKING, Type, TypeVar, Union

from pydantic.v1 import BaseModel

T = TypeVar("T", bound=BaseModel)

# This is dirty, but required for autocompletion:
# https://stackoverflow.com/questions/62884543/pydantic-autocompletion-in-vs-code
# Ideally, solved by custom templates in the future:
# https://github.com/koxudaxi/datamodel-code-generator/issues/860
# ToDo: Still needed?

if TYPE_CHECKING:
    from dataclasses import dataclass as _basemodel_decorator
else:
    _basemodel_decorator = lambda x: x  # noqa: E731


def custom_issubclass(obj: Union[type, T], class_name: str) -> bool:
    """
    Custom issubclass function that checks if the object is a subclass of a class
    with the given name.

    Parameters
    ----------
    obj : object
        The object to check.
    class_name : str
        The name of the class to check against.

    Returns
    -------
    bool
        True if the object is a subclass of the class with the given name,
        False otherwise.
    """

    def check_bases(cls, name):
        if hasattr(cls, "__name__") and cls.__name__ == name:
            return True
        if not hasattr(cls, "__bases__"):
            return False
        for base in cls.__bases__:
            if check_bases(base, name):
                return True
        return False

    return check_bases(obj, class_name)


def custom_isinstance(obj: Union[type, T], class_name: str) -> bool:
    """
    Custom isinstance function that checks if the object is an instance of a class with
    the given name.

    Parameters
    ----------
    obj : object
        The object to check.
    class_name : str
        The name of the class to check against.

    Returns
    -------
    bool
        True if the object is an instance of the class with the given name,
        False otherwise.
    """
    if not hasattr(obj, "__class__"):
        return False

    return custom_issubclass(obj.__class__, class_name)


@_basemodel_decorator
class OswBaseModel(BaseModel):

    class Config:
        strict = False  # Additional fields are allowed
        validate_assignment = True  # Ensures that the assignment of a value to a
        # field is validated

    def full_dict(self, **kwargs):  # extent BaseClass export function
        d = super().dict(**kwargs)
        for key in ("_osl_template", "_osl_footer"):
            if hasattr(self, key):
                d[key] = getattr(self, key)
                # Include selected private properties. note: private properties are not
                #  considered as discriminator
        return d

    def cast(self, cls: Union[Type[T], type], **kwargs) -> T:
        """Casting self into target class

        Parameters
        ----------
            cls
                target class
            kwargs
                additional attributes to be set

        Returns
        -------
        instance of target class
        """
        combined_args = {**self.dict(), **kwargs}
        del combined_args["type"]
        return cls(**combined_args)

    def cast_none_to_default(self, cls: Union[Type[T], type], **kwargs) -> T:
        """Casting self into target class. If the passed attribute is None or solely
        includes None values, the attribute is not passed to the instance of the
        target class, which will then fall back to the default."""

        def test_if_empty_list_or_none(obj) -> bool:
            if obj is None:
                return True
            elif isinstance(obj, list):
                if len(obj) == 0:
                    return True
                elif len([item for item in obj if item is not None]) == 0:
                    return True
            return False

        self_args = {
            k: v for k, v in self.dict().items() if not test_if_empty_list_or_none(v)
        }
        combined_args = {**self_args, **kwargs}
        if "type" in combined_args:
            del combined_args["type"]
        return cls(**combined_args)

    def get_uuid(self) -> Union[str, None]:
        return getattr(self, "uuid", None)

    def get_osw_id(self) -> Union[str, None]:
        osw_id = getattr(self, "osw_id", None)
        uuid = self.get_uuid()
        from_uuid = None if uuid is None else f"OSW{str(uuid).replace('-', '')}"
        if osw_id is None:
            return from_uuid
        if osw_id != from_uuid:
            raise ValueError(f"OSW-ID does not match UUID: {osw_id} != {from_uuid}")
        return osw_id

    def get_namespace(self) -> Union[str, None]:
        """Determines the wiki namespace based on the entity's type/class

        Returns
        -------
            The namespace as a string or None if the namespace could not be determined
        """
        namespace = None

        if hasattr(self, "meta") and self.meta and self.meta.wiki_page:
            if self.meta.wiki_page.namespace:
                namespace = self.meta.wiki_page.namespace

        if namespace is None:
            if custom_issubclass(self, "Entity"):
                namespace = "Category"
            elif custom_isinstance(self, "Category"):
                namespace = "Category"
            elif custom_issubclass(self, "Characteristic"):
                namespace = "Category"
            elif custom_isinstance(self, "Item"):
                namespace = "Item"
            elif custom_isinstance(self, "Property"):
                namespace = "Property"
            elif custom_isinstance(self, "WikiFile"):
                namespace = "File"

        return namespace

    def get_title(self) -> Union[str, None]:
        title = None

        if hasattr(self, "meta") and self.meta and self.meta.wiki_page:
            if self.meta.wiki_page.title:
                title = self.meta.wiki_page.title

        if title is None:
            title = self.get_osw_id()

        return title

    def get_iri(self) -> Union[str, None]:
        """Determines the IRI / wiki full title (namespace:title) based on the entity's
        data

        Returns
        -------
            The full title as a string or None if the title could not be determined.
        """
        namespace = self.get_namespace()
        title = self.get_title()
        if namespace is not None and title is not None:
            return namespace + ":" + title
        elif title is not None:
            return title


class Ontology(OswBaseModel):
    iri: str
    prefix: str
    name: str
    prefix_name: str
    link: str
