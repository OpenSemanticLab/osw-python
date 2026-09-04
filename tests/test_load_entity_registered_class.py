"""Unit tests for OSW.load_entity() preferring an already registered class.

Regression guard for #138: load_entity() used to decide whether to compile a
class for a category by checking ``hasattr(model, cls_name)``, keyed by class
name and only looking inside ``osw.model.entity``. This missed classes from
packaged modules (e.g. ``opensemantic.base.v1._model.Database``) that are
already registered for that category IRI in oold's type registry
(``oold.model.v1._types``), causing load_entity() to silently compile and use
a different, incomplete class instead.

These tests run fully offline: WtSite.get_page() is fed pages through
``offline_pages`` (see ``osw.wtsite.WtSite.GetPageParam``), so no network or
wiki credentials are required.
"""

import json
import threading
import uuid as uuid_module
from typing import Any, Dict, Union

from oold.model.v1 import _types as oold_type_registry
from opensemantic.base.v1 import Database

import osw.model.entity as model
from osw.core import OSW
from osw.utils.wiki import remove_empty
from osw.wtsite import WtPage, WtSite


class OfflineWtPage(WtPage):
    """A WtPage that pretends to exist without touching a wiki."""

    def __init__(self, wtSite: Any = None, title: str = None):
        self.wtSite = wtSite
        self.title = title
        self.exists = True
        self._original_content = ""
        self.changed: bool = False
        self._dict = []
        self._slots: Dict[str, Union[str, dict]] = {"main": ""}
        self._slots_changed: Dict[str, bool] = {"main": False}
        self._content_model: Dict[str, str] = {"main": "wikitext"}


class _FakeConnection:
    """Just enough of a requests session for WtSite._clear_cookies()."""

    cookies = []


class _FakeMwSite:
    connection = _FakeConnection()


def make_offline_wtsite() -> WtSite:
    """A WtSite that never touches the network (bypasses __init__)."""
    ws = WtSite.__new__(WtSite)
    ws._page_cache = {}
    ws._cache_enabled = False
    ws._session_lock = threading.RLock()
    ws._site = _FakeMwSite()
    return ws


def make_page_for_entity(entity) -> OfflineWtPage:
    """Build an offline page whose jsondata slot holds the serialized entity."""
    page = OfflineWtPage(title=f"Item:{OSW.get_osw_id(entity.uuid)}")
    jsondata = json.loads(entity.json(exclude_none=True))
    remove_empty(jsondata)
    page.set_slot_content("jsondata", jsondata)
    return page


def make_schema_page(category: str, cls_name: str) -> OfflineWtPage:
    """Build an offline page holding the jsonschema slot for a category."""
    page = OfflineWtPage(title=category)
    page.set_slot_content("jsonschema", {"title": cls_name})
    return page


def make_isolated_cls(name: str, base=model.Item):
    """Build a model.Item subclass registered under its own private category IRI.

    Overriding schema_extra's title/uuid makes get_cls_iri() derive a fresh
    "Category:OSW<uuid>" IRI for this class alone, so defining it cannot
    clobber the registration of any real category (e.g. "Category:Item").
    """
    namespace = {
        "Config": type(
            "Config",
            (base.Config,),
            {
                "schema_extra": {
                    **base.Config.schema_extra,
                    "title": name,
                    "uuid": str(uuid_module.uuid4()),
                }
            },
        ),
        "__qualname__": name,
    }
    return type(base)(name, (base,), namespace)


def test_load_entity_prefers_registered_class_over_generated_one():
    """A class already registered for the category IRI is used as-is, and no
    replacement class is compiled into osw.model.entity for it."""
    assert not hasattr(model, "Database")

    db = Database(name="TestDb", label=[model.Label(text="Test Db")])
    category = db.type[0]
    entity_page = make_page_for_entity(db)
    schema_page = make_schema_page(category, "Database")

    osw_obj = OSW(site=make_offline_wtsite())

    result = osw_obj.load_entity(
        OSW.LoadEntityParam(
            titles=[entity_page.title],
            autofetch_schema=True,
            offline_pages={
                entity_page.title: entity_page,
                category: schema_page,
            },
        )
    )

    entity = result.entities[0]
    assert type(entity) is Database
    # the packaged class was used directly, nothing was compiled
    assert not hasattr(model, "Database")


def test_load_entity_falls_back_to_generated_class_when_nothing_registered():
    """A category with nothing registered in oold's type registry still gets
    the class already present in osw.model.entity, exactly like before."""
    category = "Category:OSWFakeCategoryNotRegistered00000000000000"
    cls_name = "FakeGeneratedClass"
    assert oold_type_registry.get(category) is None

    fake_cls = make_isolated_cls(cls_name)
    setattr(model, cls_name, fake_cls)
    try:
        entity_page = OfflineWtPage(title="Item:OSWFakeEntity0000000000000000000000000")
        jsondata = {
            "type": [category],
            "uuid": "00000000-0000-0000-0000-000000000000",
            "name": "x",
            "label": [{"text": "x"}],
        }
        remove_empty(jsondata)
        entity_page.set_slot_content("jsondata", jsondata)
        schema_page = make_schema_page(category, cls_name)

        osw_obj = OSW(site=make_offline_wtsite())

        result = osw_obj.load_entity(
            OSW.LoadEntityParam(
                titles=[entity_page.title],
                autofetch_schema=True,
                offline_pages={
                    entity_page.title: entity_page,
                    category: schema_page,
                },
            )
        )

        entity = result.entities[0]
        assert type(entity) is fake_cls
    finally:
        delattr(model, cls_name)


def test_load_entity_ignores_a_registered_subclass_of_the_model_class():
    """osw's own controllers and result wrappers (WikiFileController,
    UploadFileResult, ...) inherit the category IRI of the model class they
    extend, and oold's registry keeps whichever class was defined last. Such a
    specialization needs fields a plain page does not carry, so load_entity()
    must fall back to the canonical class in osw.model.entity.
    """
    category = "Category:OSWSubclassTest000000000000000000000000"
    cls_name = "SubclassTestBase"

    base_cls = make_isolated_cls(cls_name)
    # a controller-like specialization that additionally requires a field the
    # page's jsondata does not provide, mirroring UploadFileResult.source
    specialized_cls = type(base_cls)(
        "SubclassTestController",
        (base_cls,),
        {"__annotations__": {"source": str}, "__qualname__": "SubclassTestController"},
    )
    setattr(model, cls_name, base_cls)
    oold_type_registry[category] = specialized_cls
    try:
        entity_page = OfflineWtPage(
            title="Item:OSWSubclassEntity0000000000000000000000000"
        )
        jsondata = {
            "type": [category],
            "uuid": "22222222-2222-2222-2222-222222222222",
            "name": "x",
            "label": [{"text": "x"}],
        }
        remove_empty(jsondata)
        entity_page.set_slot_content("jsondata", jsondata)
        schema_page = make_schema_page(category, cls_name)

        osw_obj = OSW(site=make_offline_wtsite())

        result = osw_obj.load_entity(
            OSW.LoadEntityParam(
                titles=[entity_page.title],
                autofetch_schema=True,
                offline_pages={
                    entity_page.title: entity_page,
                    category: schema_page,
                },
            )
        )

        assert type(result.entities[0]) is base_cls
    finally:
        delattr(model, cls_name)
        oold_type_registry.pop(category, None)


def test_load_entity_warns_on_registry_conflict(monkeypatch, caplog):
    """If the class about to be used for a category differs from whatever is
    now registered for that IRI, load_entity() logs a warning instead of
    silently letting the mismatch pass."""
    category = "Category:OSWConflictTest000000000000000000000000"
    cls_name = "ConflictGeneratedClass"
    assert oold_type_registry.get(category) is None

    generated_cls = make_isolated_cls(cls_name)
    other_cls = make_isolated_cls("OtherRegisteredClass")

    def fake_fetch_schema(self, fetchSchemaParam=None):
        # Simulate fetch_schema() compiling a class and importing it into
        # osw.model.entity, while a *different* class ends up holding the
        # oold registry slot for the same category.
        setattr(model, cls_name, generated_cls)
        oold_type_registry[category] = other_cls

    monkeypatch.setattr(OSW, "fetch_schema", fake_fetch_schema)

    try:
        entity_page = OfflineWtPage(
            title="Item:OSWConflictEntity00000000000000000000000000"
        )
        jsondata = {
            "type": [category],
            "uuid": "11111111-1111-1111-1111-111111111111",
            "name": "x",
            "label": [{"text": "x"}],
        }
        remove_empty(jsondata)
        entity_page.set_slot_content("jsondata", jsondata)
        schema_page = make_schema_page(category, cls_name)

        osw_obj = OSW(site=make_offline_wtsite())

        result = osw_obj.load_entity(
            OSW.LoadEntityParam(
                titles=[entity_page.title],
                autofetch_schema=True,
                offline_pages={
                    entity_page.title: entity_page,
                    category: schema_page,
                },
            )
        )

        entity = result.entities[0]
        assert type(entity) is generated_cls
        assert any(
            "claims the oold type registry slot" in record.message
            for record in caplog.records
        )
    finally:
        if hasattr(model, cls_name):
            delattr(model, cls_name)
        oold_type_registry.pop(category, None)
