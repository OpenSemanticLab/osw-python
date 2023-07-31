import osw.model.entity as model
from osw.utils.strings import pascal_case
from osw.utils.wiki import get_namespace


def test_get_entity_namespace():
    class DummyClass(model.Entity):
        pass

    assert get_namespace(DummyClass) == "Category"

    e = model.Entity(label=[model.Label(text="MyItem")])
    assert get_namespace(e) is None

    # e = model.Item(label=[model.Label(text="MyItem")])
    # assert get_namespace(e) == "Item"

    # not yet loaded on default
    # e = model.Category(label=[model.Label(text="MyItem")])
    # assert get_namespace(e) == "Category"

    # e = model.Property(label=[model.Label(text="MyItem")])
    # assert get_namespace(e) == "Property"

    # e = model.WikiFile(label=[model.Label(text="MyItem")])
    # assert get_namespace(e) == "File"


def test_strings_pascalcase():
    assert pascal_case("my string") == "MyString"
    assert pascal_case("my_string") == "MyString"
    assert pascal_case("MyString") == "MyString"
