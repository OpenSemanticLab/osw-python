"""
This module is to be imported in the dynamically created and updated entity.py module.
"""

from typing import TYPE_CHECKING, Literal, Optional, Type, TypeVar, Union
from uuid import UUID
from warnings import warn

from pydantic.v1 import BaseModel, Field, constr

from osw.custom_types import NoneType
from osw.utils.strings import pascal_case

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
        # strict = False
        # Additional fields are allowed
        validate_assignment = True
        # Ensures that the assignment of a value to a field is validated

    def __init__(self, **data):
        if data.get("label"):
            if not isinstance(data["label"], list):
                raise ValueError(
                    "label must be a list of Label objects",
                )
            labels = []
            for label in data["label"]:
                if isinstance(label, dict):
                    labels.append(Label(**label))
                else:
                    # The list element should be a Label object
                    labels.append(label)
            data["label"] = labels
            # Ensure that the label attribute is a list of Label objects, but use
            #  custom_isinstance to avoid circular imports and ValidationError since
            #  osw.model.entity defines its own Label class
            if not all(custom_isinstance(label, "Label") for label in data["label"]):
                raise ValueError(
                    "label must be a list of Label objects",
                )
        if data.get("name") is None and "label" in data:
            data["name"] = pascal_case(data["label"][0].text)
        super().__init__(**data)

    def full_dict(self, **kwargs):  # extent BaseClass export function
        d = super().dict(**kwargs)
        for key in ("_osl_template", "_osl_footer"):
            if hasattr(self, key):
                d[key] = getattr(self, key)
                # Include selected private properties. note: private properties are not
                #  considered as discriminator
        return d

    def cast(
        self,
        cls: Union[Type[T], type],
        none_to_default: bool = False,
        remove_extra: bool = False,
        silent: bool = True,
        **kwargs,
    ) -> T:
        """Casting self into target class

        Parameters
        ----------
        cls
            target class
        kwargs
            additional attributes to be set
        none_to_default
            If True, attributes that are None will be set to their default value
        remove_extra
            If True, extra attributes that are passed to the constructor are removed
        silent
            If True, no warnings are printed
        Returns
        -------
        instance of target class
        """

        def empty_list_or_none(
            obj: Union[
                NoneType,
                list,
            ]
        ) -> bool:
            if obj is None:
                return True
            elif isinstance(obj, list):
                if len(obj) == 0:
                    return True
                elif len([item for item in obj if item is not None]) == 0:
                    return True
            return False

        combined_args = {**self.dict(), **kwargs}
        none_args = []
        if none_to_default:
            reduced = {}
            for k, v in combined_args.items():
                if empty_list_or_none(v):
                    none_args.append(k)
                else:
                    reduced[k] = v
            combined_args = reduced
        extra_args = []
        if remove_extra:
            reduced = {}
            for k, v in combined_args.items():
                if k not in cls.__fields__.keys():
                    extra_args.append(k)
                else:
                    reduced[k] = v
            combined_args = reduced
        if not silent:
            if none_to_default and none_args:
                warn(f"Removed attributes with None or empty list values: {none_args}")
            if remove_extra and extra_args:
                warn(f"Removed extra attributes: {extra_args}")
        if "type" in combined_args:
            del combined_args["type"]
        return cls(**combined_args)

    def cast_none_to_default(self, cls: Union[Type[T], type], **kwargs) -> T:
        """Casting self into target class. If the passed attribute is None or solely
        includes None values, the attribute is not passed to the instance of the
        target class, which will then fall back to the default."""

        return self.cast(cls, none_to_default=True, **kwargs)

    def get_uuid(self) -> Union[str, UUID, NoneType]:
        """Getter for the attribute 'uuid' of the entity

        Returns
        -------
            The uuid as a string or None if the uuid could not be determined
        """
        return getattr(self, "uuid", None)

    def get_osw_id(self) -> Union[str, NoneType]:
        """Determines the OSW-ID based on the entity's uuid.

        Returns
        -------
            The OSW-ID as a string or None if the OSW-ID could not be determined
        """
        return get_osw_id(self)

    def get_namespace(self) -> Union[str, NoneType]:
        """Determines the wiki namespace based on the entity's type/class

        Returns
        -------
            The namespace as a string or None if the namespace could not be determined
        """
        return get_namespace(self)

    def get_title(self) -> Union[str, NoneType]:
        """Determines the wiki page title based on the entity's data

        Returns
        -------
            The title as a string or None if the title could not be determined
        """
        return get_title(self)

    def get_iri(self) -> Union[str, NoneType]:
        """Determines the IRI / wiki full title (namespace:title) based on the entity's
        data

        Returns
        -------
            The full title as a string or None if the title could not be determined.
        """
        return get_full_title(self)


def get_osw_id(entity: Union[OswBaseModel, Type[OswBaseModel]]) -> Union[str, NoneType]:
    """Determines the OSW-ID based on the entity's data - either from the entity's
    attribute 'osw_id' or 'uuid'.

    Parameters
    ----------
    entity
        The entity to determine the OSW-ID for

    Returns
    -------
        The OSW-ID as a string or None if the OSW-ID could not be determined
    """
    osw_id = getattr(entity, "osw_id", None)
    uuid = entity.get_uuid()
    from_uuid = None if uuid is None else f"OSW{str(uuid).replace('-', '')}"
    if osw_id is None:
        return from_uuid
    if osw_id != from_uuid:
        raise ValueError(f"OSW-ID does not match UUID: {osw_id} != {from_uuid}")
    return osw_id


def get_namespace(
    entity: Union[OswBaseModel, Type[OswBaseModel]]
) -> Union[str, NoneType]:
    """Determines the wiki namespace based on the entity's type/class

    Parameters
    ----------
    entity
        The entity to determine the namespace for

    Returns
    -------
        The namespace as a string or None if the namespace could not be determined
    """
    namespace = None

    if hasattr(entity, "meta") and entity.meta and entity.meta.wiki_page:
        if entity.meta.wiki_page.namespace:
            namespace = entity.meta.wiki_page.namespace

    if namespace is None:
        if custom_issubclass(entity, "Entity"):
            namespace = "Category"
        elif custom_isinstance(entity, "Category"):
            namespace = "Category"
        elif custom_issubclass(entity, "Characteristic"):
            namespace = "Category"
        elif custom_isinstance(entity, "Item"):
            namespace = "Item"
        elif custom_isinstance(entity, "Property"):
            namespace = "Property"
        elif custom_isinstance(entity, "WikiFile"):
            namespace = "File"

    return namespace


def get_title(entity: OswBaseModel) -> Union[str, NoneType]:
    """Determines the wiki page title based on the entity's data

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
        title = get_osw_id(entity)

    return title


def get_full_title(entity: OswBaseModel) -> Union[str, NoneType]:
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
    elif title is not None:
        return title


class Ontology(OswBaseModel):
    iri: str
    prefix: str
    name: str
    prefix_name: str
    link: str


class Label(OswBaseModel):
    text: constr(min_length=1) = Field(..., title="Text")
    lang: Optional[Literal["en", "de"]] = Field("en", title="Lang code")
