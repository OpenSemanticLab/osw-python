"""Unit tests for the selective overwrite policy of store_entity().

These run fully offline. The merge engine (``OSW._apply_overwrite_policy``) is
exercised against a fake page, and the ``store_entity()`` dispatch is tested by
stubbing ``WtPage.init``/``WtPage.edit`` so that no network is required.

Existing coverage in ``tests/test_osl.py`` applies one policy value uniformly to
a whole entity. What is covered here instead:

* the per-property dict (``OverwriteClassParam.per_property``),
* mutating a policy object after construction,
* the class-to-policy dispatch inside ``store_entity()``,
* the option combinations that the merge engine cannot honour.
"""

import json
from typing import Any, Dict, Union

import pytest

import osw.model.entity as model
from osw.core import OSW, AddOverwriteClassOptions, OverwriteOptions
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


def make_remote_page(entity, extra=None, strip_empty=True) -> OfflineWtPage:
    """Build a page whose jsondata slot holds the serialized ``entity``."""
    page = OfflineWtPage(title=f"Item:{OSW.get_osw_id(entity.uuid)}")
    jsondata = json.loads(entity.json(exclude_none=True))
    if strip_empty:
        remove_empty(jsondata)
    if extra:
        jsondata.update(extra)
    page.set_slot_content("jsondata", jsondata)
    return page


def apply_policy(page, entity, policy, **kwargs) -> dict:
    """Run the merge engine and return the resulting jsondata."""
    return OSW._apply_overwrite_policy(
        OSW._ApplyOverwriteParam(
            page=page, entity=entity, policy=policy, inplace=False, **kwargs
        )
    ).get_slot_content("jsondata")


@pytest.fixture
def remote_and_local():
    """A stored ("remote") item and an edited ("local") copy of it."""
    remote = model.Item(
        label=[model.Label(text="Remote label")],
        name="RemoteName",
        description=[model.Label(text="Remote description")],
    )
    local = model.Item(
        uuid=remote.uuid,
        type=remote.type,
        label=[model.Label(text="Local label")],
        name="LocalName",
        description=[model.Label(text="Local description")],
    )
    return remote, local


# --------------------------------------------------------------------------
# per-property merge behaviour
# --------------------------------------------------------------------------


def test_per_property_overrides_the_class_default(remote_and_local):
    """A property listed in per_property uses its own setting, not `overwrite`."""
    remote, local = remote_and_local
    policy = OSW.OverwriteClassParam(
        model=model.Item,
        overwrite=OverwriteOptions.false,
        per_property={"name": OverwriteOptions.true},
    )
    result = apply_policy(make_remote_page(remote), local, policy)

    assert result["name"] == "LocalName"  # per_property: true
    assert result["label"][0]["text"] == "Remote label"  # fallback: false


def test_per_property_only_empty_overwrites_an_empty_remote_value():
    """`only empty` writes the local value when the remote one is empty."""
    remote = model.Item(label=[model.Label(text="Remote label")], name="RemoteName")
    local = model.Item(
        uuid=remote.uuid,
        type=remote.type,
        label=[model.Label(text="Local label")],
        name="LocalName",
        description=[model.Label(text="Local description")],
    )
    # remove_empty=False so that the empty remote value survives into the merge
    page = make_remote_page(remote, extra={"description": []}, strip_empty=False)
    policy = OSW.OverwriteClassParam(
        model=model.Item,
        overwrite=OverwriteOptions.false,
        per_property={"description": OverwriteOptions.only_empty},
    )
    result = apply_policy(page, local, policy, remove_empty=False)

    assert result["description"][0]["text"] == "Local description"
    assert result["name"] == "RemoteName"


def test_per_property_only_empty_keeps_a_non_empty_remote_value(remote_and_local):
    remote, local = remote_and_local
    policy = OSW.OverwriteClassParam(
        model=model.Item,
        overwrite=OverwriteOptions.true,
        per_property={"description": OverwriteOptions.only_empty},
    )
    result = apply_policy(make_remote_page(remote), local, policy)

    assert result["description"][0]["text"] == "Remote description"
    assert result["name"] == "LocalName"


def test_property_missing_remotely_is_added_even_when_policy_is_false(
    remote_and_local,
):
    """`false` means "do not overwrite", not "do not add"."""
    remote, local = remote_and_local
    local.iri = "http://example.com/local"
    result = apply_policy(make_remote_page(remote), local, OverwriteOptions.false)

    assert result["iri"] == "http://example.com/local"
    assert result["name"] == "RemoteName"


def test_remote_property_unknown_to_the_model_is_preserved(remote_and_local):
    """Custom remote keys survive a merge, even with `overwrite=true`."""
    remote, local = remote_and_local
    page = make_remote_page(remote, extra={"custom_key": "remote value"})
    result = apply_policy(page, local, OverwriteOptions.true)

    assert result["custom_key"] == "remote value"
    assert result["name"] == "LocalName"


# --------------------------------------------------------------------------
# mutating a policy object after construction
# --------------------------------------------------------------------------


def test_reassigning_per_property_updates_the_effective_settings():
    policy = OSW.OverwriteClassParam(model=model.Item, overwrite=OverwriteOptions.false)
    assert policy.get_overwrite_setting("name") == OverwriteOptions.false

    policy.per_property = {"name": OverwriteOptions.true}

    assert policy.get_overwrite_setting("name") == OverwriteOptions.true
    assert policy.get_overwrite_setting("label") == OverwriteOptions.false


def test_clearing_per_property_restores_the_class_default():
    policy = OSW.OverwriteClassParam(
        model=model.Item,
        overwrite=OverwriteOptions.false,
        per_property={"name": OverwriteOptions.true},
    )
    policy.per_property = None

    assert policy.get_overwrite_setting("name") == OverwriteOptions.false


def test_reassigning_overwrite_updates_the_effective_settings():
    policy = OSW.OverwriteClassParam(model=model.Item, overwrite=OverwriteOptions.false)
    policy.overwrite = OverwriteOptions.true

    assert policy.get_overwrite_setting("name") == OverwriteOptions.true


def test_reassigning_overwrite_keeps_explicit_per_property_entries():
    policy = OSW.OverwriteClassParam(
        model=model.Item,
        overwrite=OverwriteOptions.false,
        per_property={"name": OverwriteOptions.only_empty},
    )
    policy.overwrite = OverwriteOptions.true

    assert policy.get_overwrite_setting("name") == OverwriteOptions.only_empty
    assert policy.get_overwrite_setting("label") == OverwriteOptions.true


def test_a_reassigned_policy_is_honoured_by_the_merge(remote_and_local):
    """The mutation must reach the merge engine, not just the accessor."""
    remote, local = remote_and_local
    policy = OSW.OverwriteClassParam(model=model.Item, overwrite=OverwriteOptions.false)
    policy.per_property = {"name": OverwriteOptions.true}
    result = apply_policy(make_remote_page(remote), local, policy)

    assert result["name"] == "LocalName"
    assert result["label"][0]["text"] == "Remote label"


# --------------------------------------------------------------------------
# validation of the policy options
# --------------------------------------------------------------------------


def test_per_property_rejects_a_property_the_model_does_not_have():
    with pytest.raises(ValueError, match="Property not found in model"):
        OSW.OverwriteClassParam(model=model.Item, per_property={"not_a_field": True})


def test_per_property_without_a_model_reports_the_missing_model():
    """A missing `model` must be a validation error, not an AttributeError."""
    # an AttributeError would escape pytest.raises(ValueError) and fail here
    with pytest.raises(ValueError) as exc_info:
        OSW.OverwriteClassParam(per_property={"name": True})

    assert "model" in str(exc_info.value)


@pytest.mark.parametrize(
    "option",
    [AddOverwriteClassOptions.replace_remote, AddOverwriteClassOptions.keep_existing],
)
def test_per_property_cannot_be_combined_with_a_whole_entity_option(option):
    """`replace remote` / `keep existing` act on the whole entity.

    The merge engine short-circuits on them, so any per_property setting would
    be silently discarded. Reject the combination instead.
    """
    with pytest.raises(ValueError, match="per_property"):
        OSW.OverwriteClassParam(
            model=model.Item,
            overwrite=option,
            per_property={"name": OverwriteOptions.true},
        )


def test_per_property_cannot_be_added_to_a_whole_entity_option():
    """The combination stays rejected when it is built up by assignment."""
    policy = OSW.OverwriteClassParam(
        model=model.Item, overwrite=AddOverwriteClassOptions.replace_remote
    )
    with pytest.raises(ValueError, match="per_property"):
        policy.per_property = {"name": OverwriteOptions.true}


def test_overwrite_cannot_be_switched_to_a_whole_entity_option():
    policy = OSW.OverwriteClassParam(
        model=model.Item,
        overwrite=OverwriteOptions.false,
        per_property={"name": OverwriteOptions.true},
    )
    with pytest.raises(ValueError, match="per_property"):
        policy.overwrite = AddOverwriteClassOptions.keep_existing


def test_whole_entity_option_is_fine_without_per_property():
    policy = OSW.OverwriteClassParam(
        model=model.Item, overwrite=AddOverwriteClassOptions.replace_remote
    )

    assert policy.overwrite == AddOverwriteClassOptions.replace_remote


def test_overwrite_none_falls_back_to_the_field_default():
    """`None` is not a policy; it must not silently disable every setting."""
    policy = OSW.OverwriteClassParam(model=model.Item, overwrite=None)

    assert policy.overwrite == OverwriteOptions.false
    assert policy.get_overwrite_setting("name") == OverwriteOptions.false
    assert policy.get_overwrite_setting("unknown_property") == OverwriteOptions.false


def test_the_none_sentinel_falls_back_to_the_field_default():
    """`AddOverwriteClassOptions.none` is documented as not being a choice."""
    policy = OSW.OverwriteClassParam(
        model=model.Item, overwrite=AddOverwriteClassOptions.none
    )

    assert policy.overwrite == OverwriteOptions.false
    assert policy.get_overwrite_setting("name") == OverwriteOptions.false


@pytest.mark.parametrize("value", [None, AddOverwriteClassOptions.none])
def test_assigning_a_non_policy_value_also_falls_back(value):
    """Construction and assignment must normalise the same way."""
    policy = OSW.OverwriteClassParam(model=model.Item, overwrite=OverwriteOptions.true)
    policy.overwrite = value

    assert policy.overwrite == OverwriteOptions.false
    assert policy.get_overwrite_setting("name") == OverwriteOptions.false


def test_the_none_sentinel_is_accepted_alongside_per_property():
    """It normalises to a real policy, so it is not a whole-entity option."""
    policy = OSW.OverwriteClassParam(
        model=model.Item,
        overwrite=OverwriteOptions.true,
        per_property={"name": OverwriteOptions.only_empty},
    )
    policy.overwrite = AddOverwriteClassOptions.none

    assert policy.get_overwrite_setting("name") == OverwriteOptions.only_empty
    assert policy.get_overwrite_setting("label") == OverwriteOptions.false


def test_a_rejected_assignment_leaves_the_policy_unchanged():
    """A rejected value must not sit there waiting to take effect later."""
    policy = OSW.OverwriteClassParam(
        model=model.Item, overwrite=AddOverwriteClassOptions.replace_remote
    )
    with pytest.raises(ValueError):
        policy.per_property = {"name": OverwriteOptions.true}

    assert policy.per_property is None
    # the rejected dict must not become live once `overwrite` is made legal
    policy.overwrite = OverwriteOptions.false
    assert policy.get_overwrite_setting("name") == OverwriteOptions.false


def test_overwrite_none_keeps_the_remote_value(remote_and_local):
    remote, local = remote_and_local
    result = apply_policy(
        make_remote_page(remote),
        local,
        OSW.OverwriteClassParam(model=model.Item, overwrite=None),
    )

    assert result["name"] == "RemoteName"


# --------------------------------------------------------------------------
# store_entity() dispatch
# --------------------------------------------------------------------------


def _stub_page_io(monkeypatch, exists: bool):
    """Make WtPage usable without a wiki and record every edit() call."""
    monkeypatch.setattr(WtPage, "init", lambda self: setattr(self, "exists", exists))
    monkeypatch.setattr(
        WtPage, "get_url", lambda self: f"https://example.org/{self.title}"
    )
    edited = []
    monkeypatch.setattr(WtPage, "edit", lambda self, *a, **k: edited.append(self.title))
    return edited


@pytest.fixture
def offline_osw(monkeypatch):
    _stub_page_io(monkeypatch, exists=False)
    return OSW.construct(site=object())


def test_class_specific_policy_reaches_the_merge_engine(offline_osw, monkeypatch):
    """An entity's class picks its OverwriteClassParam out of the list."""
    seen = {}

    def spy(param):
        seen[param.page.title] = param.policy
        return param.page

    monkeypatch.setattr(OSW, "_apply_overwrite_policy", staticmethod(spy))

    item = model.Item(label=[model.Label(text="An item")])
    declared = OSW.OverwriteClassParam(
        model=model.Item,
        overwrite=OverwriteOptions.false,
        per_property={"name": OverwriteOptions.true},
    )
    offline_osw.store_entity(
        OSW.StoreEntityParam(
            entities=[item], overwrite_per_class=[declared], parallel=False
        )
    )

    (policy,) = seen.values()
    assert policy.get_overwrite_setting("name") == OverwriteOptions.true
    assert policy.get_overwrite_setting("label") == OverwriteOptions.false


def test_fallback_policy_is_used_when_no_class_matches(offline_osw, monkeypatch):
    seen = {}

    def spy(param):
        seen[param.page.title] = param.policy
        return param.page

    monkeypatch.setattr(OSW, "_apply_overwrite_policy", staticmethod(spy))

    item = model.Item(label=[model.Label(text="An item")])
    offline_osw.store_entity(
        OSW.StoreEntityParam(
            entities=[item], overwrite=OverwriteOptions.true, parallel=False
        )
    )

    (policy,) = seen.values()
    assert policy.get_overwrite_setting("name") == OverwriteOptions.true


def test_two_policies_for_the_same_class_are_rejected():
    with pytest.raises(ValueError, match="More than one OverwriteClassParam"):
        OSW.StoreEntityParam(
            entities=[model.Item(label=[model.Label(text="x")])],
            overwrite_per_class=[
                OSW.OverwriteClassParam(model=model.Item, overwrite=True),
                OSW.OverwriteClassParam(model=model.Item, overwrite=False),
            ],
        )


# --------------------------------------------------------------------------
# keep existing
# --------------------------------------------------------------------------


def test_keep_existing_does_not_edit_a_page_that_exists(monkeypatch):
    """ "keep existing" must leave an existing page completely untouched."""
    edited = _stub_page_io(monkeypatch, exists=True)
    osw_obj = OSW.construct(site=object())

    osw_obj.store_entity(
        OSW.StoreEntityParam(
            entities=[model.Item(label=[model.Label(text="Keep me")])],
            overwrite=AddOverwriteClassOptions.keep_existing,
            parallel=False,
        )
    )

    assert edited == []


def test_keep_existing_still_creates_a_page_that_does_not_exist(monkeypatch):
    edited = _stub_page_io(monkeypatch, exists=False)
    osw_obj = OSW.construct(site=object())

    osw_obj.store_entity(
        OSW.StoreEntityParam(
            entities=[model.Item(label=[model.Label(text="Create me")])],
            overwrite=AddOverwriteClassOptions.keep_existing,
            parallel=False,
        )
    )

    assert len(edited) == 1


def test_keep_existing_returns_the_page_it_skipped(monkeypatch):
    """The caller still gets the page back, so it can inspect what is stored."""
    _stub_page_io(monkeypatch, exists=True)
    osw_obj = OSW.construct(site=object())

    item = model.Item(label=[model.Label(text="Keep me")])
    result = osw_obj.store_entity(
        OSW.StoreEntityParam(
            entities=[item],
            overwrite=AddOverwriteClassOptions.keep_existing,
            parallel=False,
        )
    )

    assert f"Item:{OSW.get_osw_id(item.uuid)}" in result.pages


class _MetaCategorySite:
    """Just enough of a WtSite to drive the schema regeneration branch."""

    def __init__(self):
        meta_category = OfflineWtPage(title="Category:Category")
        meta_category.set_slot_content("schema_template", '{"title": "generated"}')
        meta_category.set_slot_content("jsondata", {})  # no subclass_of -> stop
        self._meta_category = meta_category

    def get_page(self, param):
        return WtSite.GetPageResult(pages=[self._meta_category], errors=[])


def _store_category(monkeypatch, overwrite):
    _stub_page_io(monkeypatch, exists=True)
    osw_obj = OSW.construct(site=_MetaCategorySite())
    entity = model.Item(label=[model.Label(text="A category")])
    result = osw_obj.store_entity(
        OSW.StoreEntityParam(
            entities=[entity],
            namespace="Category",
            overwrite=overwrite,
            parallel=False,
        )
    )
    return result.pages[f"Category:{OSW.get_osw_id(entity.uuid)}"]


def test_a_category_page_normally_gets_a_regenerated_schema(monkeypatch):
    """Guards the test below: the schema branch really is reached here."""
    page = _store_category(monkeypatch, OverwriteOptions.true)

    assert page.get_slot_content("jsonschema") is not None


def test_keep_existing_does_not_regenerate_the_schema_of_a_category(monkeypatch):
    """The schema branch used to run for every policy, editing a kept page."""
    page = _store_category(monkeypatch, AddOverwriteClassOptions.keep_existing)

    assert page.get_slot_content("jsonschema") is None
