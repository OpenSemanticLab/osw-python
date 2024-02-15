"""
This module is to be imported in the dynamically created and updated entity.py module.
"""
from typing import Type, TypeVar, Union

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class OswBaseModel(BaseModel):
    def full_dict(self, **kwargs):  # extent BaseClass export function
        d = super().dict(**kwargs)
        for key in ("_osl_template", "_osl_footer"):
            if hasattr(self, key):
                d[key] = getattr(self, key)
                # Include selected private properties. note: private properties are not
                #  considered as discriminator
        return d

    def cast(self, cls: Union[Type[T], type]) -> T:
        return cls(**self.dict())

    def cast_none_to_default(self, cls: Union[Type[T], type]) -> T:
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

        return cls(
            **{
                k: v
                for k, v in self.dict().items()
                if not test_if_empty_list_or_none(v)
            }
        )


class Ontology(OswBaseModel):
    iri: str
    prefix: str
    name: str
    prefix_name: str
    link: str
