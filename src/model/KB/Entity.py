# generated by datamodel-codegen:
#   filename:  Entity.json
#   timestamp: 2022-12-07T18:51:32+00:00

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field
from typing_extensions import Literal


from uuid import uuid4
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dataclasses import dataclass as _basemodel_decorator
else:
    _basemodel_decorator = lambda x: x


class OslBaseModel(BaseModel):
    def full_dict(self, **kwargs): #extent BaseClass export function
        d = super().dict(**kwargs)
        for key in ('_osl_template', '_osl_footer'):
            if hasattr(self, key): d[key] = getattr(self, key) #include selected private properites. note: private properties are not considered as discriminator 
        return d



@_basemodel_decorator
class KBEntityFooter(OslBaseModel):
    osl_template: Optional[str] = 'OslTemplate:KB/Entity/Footer'


class LangCode(Enum):
    en = 'en'
    de = 'de'


@_basemodel_decorator
class Label(OslBaseModel):
    osl_template: Optional[Literal['OslTemplate:Label']] = 'OslTemplate:Label'
    label_text: str = Field(..., title='Label')
    label_lang_code: Optional[LangCode] = Field('en', title='Lang code')


@_basemodel_decorator
class Statement(OslBaseModel):
    osl_template: Optional[Literal['OslTemplate:Statement']] = 'OslTemplate:Statement'
    label: Optional[Label] = Field(None, title='Label')
    """
    Human readable name
    """
    uuid: UUID = Field(default_factory=uuid4, title='UUID')
    subject: Optional[str] = None
    predicate: str
    object: Optional[str] = None
    substatements: Optional[List[Statement]] = Field(None, title='Substatements')


@_basemodel_decorator
class Entity(OslBaseModel):
    osl_template: Optional[Literal['OslTemplate:KB/Entity']] = 'OslTemplate:KB/Entity'
    uuid: UUID = Field(default_factory=uuid4, title='UUID')
    label: Label = Field(..., title='Label')
    """
    Human readable name
    """
    additional_labels: Optional[List[Label]] = Field(None, title='Additional Labels')
    statements: Optional[List[Statement]] = Field(None, title='Statements')
    extensions: Optional[List[Any]] = Field(None, title='Extensions')
    osl_wikitext: Optional[str] = '\n=Details=\n'
    osl_footer: Optional[KBEntityFooter] = Field(
        {'osl_template': 'OslTemplate:KB/Entity/Footer'}, title='KB/Entity/Footer'
    )


Statement.update_forward_refs()
