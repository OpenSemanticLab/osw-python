from typing import List, Set

from pydantic.v1 import BaseModel

from osw.model.entity import Item, Label


class FirstModel(Item):
    label: List[Label]
    unique_labels: Set[Label]
    """Will cast a provided list to set and will try to has the elements. After
    reworking OswBaseModel, every inheriting class, like 'Label' will have '__hash__'
    method and therefore can be used as an element of a set."""


class UnhashableLabel(BaseModel):
    text: str
    lang: str = "en"


class SecondModel(Item):
    label: List[Label]
    unique_labels: Set[UnhashableLabel]
    """Will try to cast a provided list to set and fail because elements
    (UnhashableLabel) are not hashable."""


def test_hashing():
    some_model = FirstModel(
        label=[Label(text="MyItem", lang="en")],
        unique_labels=[
            Label(text="MyItem", lang="en"),
            Label(text="MyItem", lang="en"),
        ],
    )
    # Pydantic should coerce the list to a set and hash the elements
    assert isinstance(some_model.unique_labels, set)
    assert some_model.unique_labels == {Label(text="MyItem", lang="en")}
    try:
        _ = SecondModel(
            label=[Label(text="MyItem", lang="en")],
            unique_labels=[
                UnhashableLabel(text="MyItem", lang="en"),
            ],
        )
    except Exception as e:
        assert e.__class__.__name__ == "TypeError"
        assert "unhashable" in str(e)
    _ = FirstModel(
        label=[Label(text="MyItem", lang="en")],
        unique_labels=[
            Label(text="MyItem", lang="en"),
            Label(text="MyItem", lang="de"),
            Label(text="Mein Gegenstand", lang="de"),
        ],
    )
    # Should not cause any errors


if __name__ == "__main__":
    test_hashing()
