"""Offline harness for the jsonschema regeneration of store_entity().

store_entity() reads the schema templates of the meta categories from the wiki.
FakeSite serves them from a dict, so the schema generation can be exercised
without network. It is shared by the test modules that cover the generation,
instead of a private copy per module.
"""

import json

from opensemantic.core.v1 import CharacteristicType

import osw.model.entity as model
from osw.core import OSW
from osw.wtsite import WtPage

META_UUID = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
META_CATEGORY = "Category:OSW0a1b2c3d4e5f4a6b8c7d9e0f1a2b3c4d"
PARENT_UUID = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
PARENT_CATEGORY = "Category:OSW1a2b3c4d5e6f4a7b8c9d0e1f2a3b4c5d"
CHARACTERISTIC_TYPE = "Category:OSWffe74f291d354037b318c422591c5023"
GEN_POINTER = "#/$defs/generated"


def schema_ref(title):
    return f"/wiki/{title}?action=raw&slot=jsonschema"


class FakePage:
    def __init__(self, title, template, schema):
        self.title = title
        self._slots = {
            "schema_template": template,
            "jsondata": {},
            "jsonschema": schema,
        }

    def get_slot_content(self, slot_key, clone=True):
        # the signature mirrors WtPage.get_slot_content, which the code under
        # test may call with the clone argument
        return self._slots[slot_key]


class _FakeGetPageResult:
    def __init__(self, pages):
        self.pages = pages


class FakeSite:
    """Serves the meta categories whose templates the generation applies.

    Like in the wiki, the templates are collected along the allOf chain of the
    meta category schema, so the meta category refers to CharacteristicType when
    `definitions` is set, which selects the definitions section mode.

    parent_template adds a second meta category ahead of the first one, which is
    how a template that fails after another one already produced a schema is
    reproduced.
    """

    def __init__(self, template, definitions, parent_template=None):
        self.template = template
        self.definitions = definitions
        self.parent_template = parent_template

    def _meta_schema(self):
        schema = {"uuid": META_UUID, "allOf": []}
        if self.parent_template is not None:
            schema["allOf"].append({"$ref": schema_ref(PARENT_CATEGORY)})
        if self.definitions:
            schema["allOf"].append({"$ref": schema_ref(CHARACTERISTIC_TYPE)})
        return schema

    def _page(self, title):
        if title == META_CATEGORY:
            return FakePage(title, self.template, self._meta_schema())
        if title == PARENT_CATEGORY:
            return FakePage(title, self.parent_template, {"uuid": PARENT_UUID})
        if title == CHARACTERISTIC_TYPE:
            return FakePage(
                title, None, {"uuid": "ffe74f29-1d35-4037-b318-c422591c5023"}
            )
        return FakePage(title, None, {})

    def get_page(self, param):
        return _FakeGetPageResult([self._page(t) for t in param.titles])


def make_store(monkeypatch):
    """Returns a callable that runs store_entity() offline and gives the slot.

    The overwrite policy is wrapped rather than bypassed, so that the stored
    jsonschema slot the generation has to merge into is on the page when
    store_entity() reads it.

    With offline=False the page counts as existing and the wiki calls of the
    save are stubbed, which is the only way to reach the branches that test
    page.exists and the overwrite policy.
    """
    original_policy = OSW._apply_overwrite_policy

    def _store(
        entity,
        template,
        stored,
        definitions=None,
        parent_template=None,
        overwrite=None,
        offline=True,
    ):
        if definitions is None:
            # characteristics select the definitions section mode in the wiki
            definitions = isinstance(entity, CharacteristicType)
        if not offline:
            monkeypatch.setattr(
                WtPage, "init", lambda self: setattr(self, "exists", True)
            )
            monkeypatch.setattr(WtPage, "edit", lambda self, *a, **kw: None)
            monkeypatch.setattr(OSW, "_get_missing_page_titles", lambda s, t: [])
            # the success log of store_entity_() builds the page url from the
            # mwclient site, which the fake does not have
            monkeypatch.setattr(
                WtPage, "get_url", lambda self: f"https://example.invalid/{self.title}"
            )

        def policy_with_stored_schema(param):
            if stored is not None:
                content = json.loads(json.dumps(stored)) if stored else stored
                param.page.set_slot_content("jsonschema", content)
            return original_policy(param)

        monkeypatch.setattr(
            OSW, "_apply_overwrite_policy", staticmethod(policy_with_stored_schema)
        )
        osw_obj = OSW.construct(
            site=FakeSite(template, definitions, parent_template=parent_template)
        )
        store_param = OSW.StoreEntityParam(
            entities=[entity],
            namespace="Category",
            meta_category_title=META_CATEGORY,
            offline=offline,
            **({} if overwrite is None else {"overwrite": overwrite}),
        )
        result = osw_obj.store_entity(store_param)
        (page,) = result.pages.values()
        assert isinstance(page, WtPage)
        return page.get_slot_content("jsonschema")

    return _store


def characteristic():
    return CharacteristicType(
        uuid="efad8086-4a76-47ca-b278-f5f944e5754b",
        name="TestCharacteristic",
        label=[{"text": "Test Characteristic"}],
        # the default resolves a superclass from a wiki, and oold 2 rejects an
        # empty list for this required field
        subclass_of=[CHARACTERISTIC_TYPE],
    )


def category():
    # store_entity() selects ROOT_LEVEL mode for any entity that is not a
    # characteristic, so a plain Item stored in the Category namespace suffices
    return model.Item(
        uuid="0d0c1c35-4c4d-4e3a-9c9a-6f4a1b2c3d4e",
        name="TestCategory",
        label=[model.Label(text="Test Category")],
    )
