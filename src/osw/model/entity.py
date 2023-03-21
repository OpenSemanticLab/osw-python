# generated by datamodel-codegen:
#   filename:  Item.json
#   timestamp: 2023-01-23T06:27:29+00:00

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field
from typing_extensions import Literal


class LangCode(Enum):
    en = "en"
    de = "de"


from typing import TYPE_CHECKING, Type, TypeVar
from uuid import uuid4

if TYPE_CHECKING:
    from dataclasses import dataclass as _basemodel_decorator
else:
    _basemodel_decorator = lambda x: x  # noqa: E731


T = TypeVar("T", bound=BaseModel)


class OswBaseModel(BaseModel):
    def full_dict(self, **kwargs):  # extent BaseClass export function
        d = super().dict(**kwargs)
        for key in ("_osl_template", "_osl_footer"):
            if hasattr(self, key):
                d[key] = getattr(
                    self, key
                )  # include selected private properites. note: private properties are not considered as discriminator
        return d

    def cast(self, cls: Type[T]) -> T:
        return cls(**self.dict())


@_basemodel_decorator
class Label(OswBaseModel):
    text: str = Field(..., title="Text")
    lang: Optional[LangCode] = Field("en", title="Lang code")


class LangCode1(Enum):
    en = "en"
    de = "de"


@_basemodel_decorator
class Description(OswBaseModel):
    text: str = Field(..., title="Text")
    lang: Optional[LangCode1] = Field("en", title="Lang code")


@_basemodel_decorator
class Statement(OswBaseModel):
    osl_template: Optional[Literal["OslTemplate:Statement"]] = "OslTemplate:Statement"
    label: Optional[Label] = Field(None, title="Label")
    """
    Human readable name
    """
    uuid: UUID = Field(default_factory=uuid4, title="UUID")
    subject: Optional[str] = None
    predicate: str
    object: Optional[str] = None
    substatements: Optional[List[Statement]] = Field(None, title="Substatements")


@_basemodel_decorator
class Entity(OswBaseModel):
    uuid: UUID = Field(default_factory=uuid4, title="UUID")
    label: Label = Field(..., title="Label")
    """
    Human readable name
    """
    query_label: Optional[str] = Field(None, title="Label")
    additional_labels: Optional[List[Label]] = Field(None, title="Additional Labels")
    description: Optional[List[Description]] = Field(None, title="Description")
    image: Optional[str] = Field(None, title="Image")
    statements: Optional[List[Statement]] = Field(None, title="Statements")
    extensions: Optional[List[Any]] = Field(None, title="Extensions")


class Item(Entity):
    type: Optional[List[str]] = Field(
        ["Category:Item"], min_length=1, title="Types/Categories"
    )


Statement.update_forward_refs()