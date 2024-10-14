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


@_basemodel_decorator
class OswBaseModel(BaseModel):
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
        del combined_args["type"]
        return cls(**combined_args)


class Ontology(OswBaseModel):
    iri: str
    prefix: str
    name: str
    prefix_name: str
    link: str
