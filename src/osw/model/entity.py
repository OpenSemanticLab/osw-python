# generated by datamodel-codegen:
#   filename:  Item.json
#   timestamp: 2024-09-12T12:35:11+00:00

from __future__ import annotations

from typing import Any, List, Literal, Optional, Set, Union
from uuid import UUID, uuid4

from pydantic.v1 import Field, constr

from osw.model.static import OswBaseModel


class ReadAccess(OswBaseModel):
    level: Optional[Literal["public", "internal", "restricted"]] = Field(
        None, title="Level"
    )


class AccessRestrictions(OswBaseModel):
    read: Optional[ReadAccess] = Field(None, title="Read access")


class Label(OswBaseModel):
    text: constr(min_length=1) = Field(..., title="Text")
    lang: Optional[Literal["en", "de"]] = Field("en", title="Lang code")


class Description(Label):
    pass


class WikiPage(OswBaseModel):
    """
    The wiki page containing this entity
    """

    title: Optional[str] = Field(None, title="Title")
    """
    The page title
    """
    namespace: Optional[str] = Field(None, example="Category", title="Namespace")
    """
    The page namespace
    """


class Meta(OswBaseModel):
    wiki_page: Optional[WikiPage] = Field(None, title="Wiki page")
    """
    The wiki page containing this entity
    """
    change_id: Optional[List[str]] = Field(None, title="Change IDs")
    """
    To keep track of concerted changes
    """


class Entity(OswBaseModel):
    rdf_type: Optional[Set[str]] = Field(None, title="Additional RDF type(s)")
    """
    Declares additional type(s) for this entity, e.g., to state that this entity has the same meaning as a term in a controlled vocabulary or ontology. This property is synonymous to the schema:additionalType and owl:sameAs. The default syntax is ontology:TermName. The ontology prefix has to be defined in the @context of the Entity, the category or any of the parent categories. The term name has to be a valid identifier in the ontology.
    """
    uuid: UUID = Field(default_factory=uuid4, title="UUID")
    iri: Optional[str] = Field(None, title="IRI")
    """
    The Internationalized Resource Identifier (IRI) of this entity
    """
    name: Optional[str] = Field(None, title="Technical name")
    """
    Technical / Machine compatible name
    """
    label: List[Label] = Field(..., min_items=1, title="Label(s)")
    """
    At least one label is required.
    """
    short_name: Optional[List[Label]] = Field(None, title="Short name(s)")
    """
    Abbreviation, Acronym, etc.
    """
    query_label: Optional[str] = Field(None, title="Query label")
    description: Optional[List[Description]] = Field(None, title="Description")
    image: Optional[str] = Field(None, title="Image")
    ordering_categories: Optional[List[str]] = Field(None, title="Ordering categories")
    """
    Ordering categories are used to categorize instances, e.g., according to their use but not their properties. When querying for instances of a here listed ordering category, this instance will be returned. Note: Ordering categories define no properties, while 'regular' categories define properties, which an instance assigns values to.
    """
    keywords: Optional[List[str]] = Field(None, title="Keywords / Tags")
    """
    Designated to the user defined categorization of this element
    """
    based_on: Optional[List[str]] = Field(None, title="Based on")
    """
    Other entities on which this one is based, e.g. when it is created by copying
    """
    statements: Optional[
        List[Union[ObjectStatement, DataStatement, QuantityStatement]]
    ] = Field(None, title="Statements")
    attachments: Optional[List[str]] = Field(None, title="File attachments")
    meta: Optional[Meta] = None


class ObjectStatement(OswBaseModel):
    rdf_type: Optional[Any] = "rdf:Statement"
    uuid: UUID = Field(default_factory=uuid4, title="UUID")
    label: Optional[List[Label]] = Field(None, title="Label")
    """
    Human readable name
    """
    subject: Optional[str] = Field(None, title="Subject")
    substatements: Optional[
        List[Union[ObjectStatement, DataStatement, QuantityStatement]]
    ] = Field(None, title="Substatements")
    predicate: str = Field(..., title="Predicate")
    object: str = Field(..., title="Object")


class DataStatement(OswBaseModel):
    rdf_type: Optional[Any] = "rdf:Statement"
    uuid: UUID = Field(default_factory=uuid4, title="UUID")
    label: Optional[List[Label]] = Field(None, title="Label")
    """
    Human readable name
    """
    subject: Optional[str] = Field(None, title="Subject")
    substatements: Optional[
        List[Union[ObjectStatement, DataStatement, QuantityStatement]]
    ] = Field(None, title="Substatements")
    property: str = Field(..., title="Property")
    value: str = Field(..., title="Value")


class QuantityStatement(OswBaseModel):
    rdf_type: Optional[Any] = "rdf:Statement"
    uuid: UUID = Field(default_factory=uuid4, title="UUID")
    label: Optional[List[Label]] = Field(None, title="Label")
    """
    Human readable name
    """
    subject: Optional[str] = Field(None, title="Subject")
    substatements: Optional[
        List[Union[ObjectStatement, DataStatement, QuantityStatement]]
    ] = Field(None, title="Substatements")
    quantity: str = Field(..., title="Property")
    numerical_value: str = Field(..., title="Value")
    unit: str = Field(..., title="Unit")
    unit_symbol: str
    value: str = Field(..., title="Value")


class Item(Entity):
    type: Optional[List[str]] = Field(
        ["Category:Item"], min_items=1, title="Types/Categories"
    )
    entry_access: Optional[AccessRestrictions] = Field(
        None, title="Access restrictions"
    )


Entity.update_forward_refs()
ObjectStatement.update_forward_refs()
DataStatement.update_forward_refs()
QuantityStatement.update_forward_refs()
Item.update_forward_refs()
