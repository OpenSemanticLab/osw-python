import uuid

import osw.model.entity as model
from osw.utils.strings import count_match_groups, pascal_case
from osw.utils.wiki import (
    get_full_title,
    get_namespace,
    get_osw_id,
    get_title,
    get_uuid,
    is_empty,
    namespace_from_full_title,
    title_from_full_title,
)


# osw.utils.wiki
def test_get_osw_id():
    uuid_ = uuid.uuid4()
    osw_id = f"OSW{str(uuid_).replace('-', '')}"
    assert get_osw_id(uuid_) == osw_id


def test_get_uuid():
    uuid_ = uuid.uuid4()
    osw_id = f"OSW{str(uuid_).replace('-', '')}"
    assert get_uuid(osw_id) == uuid_


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


def test_get_title():
    title = "MyItem"
    namespace = "Item"
    entity = model.Item(label=[model.Label(text=title)])
    second_entity = model.Item(label=[model.Label(text=title)])
    second_entity.meta = model.Meta(
        wiki_page=model.WikiPage(title=title, namespace=namespace)
    )
    assert get_title(entity) == get_osw_id(entity.uuid)
    assert get_title(second_entity) == title


def test_get_full_title():
    title = "MyItem"
    namespace = "Item"
    entity = model.Item(label=[model.Label(text=title)])
    second_entity = model.Item(label=[model.Label(text=title)])
    second_entity.meta = model.Meta(
        wiki_page=model.WikiPage(title=title, namespace=namespace)
    )
    second_entity.meta.wiki_page.namespace = namespace
    assert get_full_title(entity) == f"Item:{get_osw_id(entity.uuid)}"
    assert get_full_title(second_entity) == f"{namespace}:{title}"


def test_namespace_from_full_title():
    full_title = "Item:MyTitle"
    assert namespace_from_full_title(full_title) == "Item"


def test_title_from_full_title():
    full_title = "Item:MyTitle"
    assert title_from_full_title(full_title) == "MyTitle"


def test_is_empty():
    assert is_empty(None)
    assert is_empty("")
    assert is_empty([])
    assert is_empty({})
    assert not is_empty("String")
    assert not is_empty(["List"])
    assert not is_empty({"Dict": "Value"})


# osw.utils.strings
def test_count_match_groups():
    pat = r"(\\d+)(\\w+)\\((\\d+)\\)"
    assert count_match_groups(pat) == 3
    pat2 = r"((\\d+)(\\w+))"
    assert count_match_groups(pat2) == 3
    pat3 = r"(File:(OSW[0-9a-fA-F]{32})((?:\.[\w-]+)*))"
    assert count_match_groups(pat3) == 3


def test_strings_pascalcase():
    assert pascal_case("my string") == "MyString"
    assert pascal_case("my_string") == "MyString"
    assert pascal_case("MyString") == "MyString"


# osw.utils.regex_pattern
def test_regex_pattern():
    """This tests the regex pattern library. For all patterns in the library, the
    test_pattern method is called. If the method does not raise an exception, the
    pattern is considered correct. If no example_str and no expected_groups are
    provided, the test_pattern method raise a type error originating from the re
    module."""
    from osw.utils.regex_pattern import REGEX_PATTERN_LIB

    for _key, pattern in REGEX_PATTERN_LIB.items():
        assert pattern.test_pattern()
