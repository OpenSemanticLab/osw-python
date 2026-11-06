"""Unit tests for load_entity()'s result shape and resolve()'s iri pairing.

Regression guard for #198: https://github.com/OpenSemanticLab/osw-python/issues/198
LoadEntityResult.entities was declared as Union[OswBaseModel, List[OswBaseModel]],
so pydantic v1 tried the bare OswBaseModel variant first and an empty list
validated as OswBaseModel() instead of staying an empty list. Separately,
OswDefaultBackend.resolve() zipped request.iris against load_entity()'s result
positionally, so a page load_entity() skipped shifted every later iri onto the
wrong entity.

These run fully offline: no site touches the network.
"""

from unittest.mock import MagicMock

from oold.backend.interface import ResolveParam

import osw.core
import osw.model.entity as model
from osw.core import OSW
from osw.wtsite import WtSite


def _make_entity(namespace: str, title: str) -> model.Item:
    entity = model.Item(label=[model.Label(text=title)])
    entity.meta = model.Meta(wiki_page=model.WikiPage(namespace=namespace, title=title))
    return entity


def _build_backend(monkeypatch):
    """Constructs an OSW instance and returns its OswDefaultBackend.

    set_resolver/set_backend are replaced so construction does not touch the
    real global oold registry; set_backend is used to capture the backend
    instance it would otherwise register.
    """
    captured = {}

    def _capture_set_backend(param):
        captured["backend"] = param.backend

    monkeypatch.setattr(osw.core, "set_resolver", lambda param: None)
    monkeypatch.setattr(osw.core, "set_backend", _capture_set_backend)

    site = MagicMock(spec=WtSite)
    OSW(site=site)

    return captured["backend"]


def test_load_entity_result_keeps_empty_list_as_list():
    result = OSW.LoadEntityResult(entities=[])

    assert result.entities == []
    assert bool(result.entities) is False
    assert len(result.entities) == 0


def test_load_entity_result_keeps_non_empty_list_and_subclass():
    item = model.Item(label=[model.Label(text="x")])

    result = OSW.LoadEntityResult(entities=[item])

    assert isinstance(result.entities, list)
    assert len(result.entities) == 1
    assert isinstance(result.entities[0], model.Item)


def test_resolve_pairs_iris_by_title_not_position(monkeypatch):
    backend = _build_backend(monkeypatch)
    good = _make_entity("Item", "OSWAlignGood")

    def _stub_load_entity(self, param):
        # "Item:OSWAlignBad" could not be built and load_entity() silently
        # skips it, so the returned list is shorter than request.iris.
        return OSW.LoadEntityResult(entities=[good])

    monkeypatch.setattr(OSW, "load_entity", _stub_load_entity)

    result = backend.resolve(
        ResolveParam(iris=["Item:OSWAlignBad", "Item:OSWAlignGood"])
    )

    # ResolveResult validates its values, which copies the entity, so compare
    # by equality rather than by identity
    assert result.nodes["Item:OSWAlignGood"] == good
    # oold indexes nodes by iri without checking for the key, and types the
    # values as Union[None, ...], so an unresolved iri maps to None
    assert result.nodes["Item:OSWAlignBad"] is None


def test_resolve_returns_all_entities_when_every_iri_resolves(monkeypatch):
    backend = _build_backend(monkeypatch)
    first = _make_entity("Item", "OSWFirst")
    second = _make_entity("Item", "OSWSecond")

    def _stub_load_entity(self, param):
        return OSW.LoadEntityResult(entities=[first, second])

    monkeypatch.setattr(OSW, "load_entity", _stub_load_entity)

    result = backend.resolve(ResolveParam(iris=["Item:OSWFirst", "Item:OSWSecond"]))

    assert result.nodes == {"Item:OSWFirst": first, "Item:OSWSecond": second}
