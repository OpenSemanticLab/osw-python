import json
from typing import Any, Dict, Union
from uuid import UUID

import osw.model.entity as model
from osw.core import OSW, AddOverwriteClassOptions, OverwriteOptions
from osw.wtsite import WtPage


class OfflineWtPage(WtPage):

    def __init__(self, wtSite: Any = None, title: str = None):
        self.wtSite = wtSite
        self.title = title

        self.exists = True  # only to fake the existence of the page for testing
        self._original_content = ""
        self._content = ""
        self.changed: bool = False
        self._dict = []
        self._slots: Dict[str, Union[str, dict]] = {"main": ""}
        self._slots_changed: Dict[str, bool] = {"main": False}
        self._content_model: Dict[str, str] = {"main": "wikitext"}


def test_osw_id_to_uuid():
    osw_id = "OSW2ea5b605c91f4e5a95593dff79fdd4a5"
    expected = UUID("2ea5b605-c91f-4e5a-9559-3dff79fdd4a5")
    result = OSW.get_uuid(osw_id)
    assert result == expected


def test_uuid_to_osw_id():
    uuid = UUID("2ea5b605-c91f-4e5a-9559-3dff79fdd4a5")
    expected = "OSW2ea5b605c91f4e5a95593dff79fdd4a5"
    result = OSW.get_osw_id(uuid)
    assert result == expected


def check_true(original: model.Entity, altered: model.Entity, stored: model.Entity):
    """Check the entity that was stored with the 'overwrite' param set to True,
    which is supposed to overwrite all existing properties of the entity in the
    OSW, but keep those not present in the altered entity."""
    assert stored.label[0].text == altered.label[0].text
    assert stored.name == altered.name
    assert stored.iri == altered.iri
    assert stored.description[0].text == altered.description[0].text
    assert stored.query_label == altered.query_label
    assert stored.image == original.image
    assert stored.attachments == altered.attachments


def check_false(original: model.Entity, altered: model.Entity, stored: model.Entity):
    """Check the entity that was stored with the 'overwrite' param set to False,
    which is supposed to keep all existing properties of the entity in the OSW,
    but add those additionally present in the altered entity."""
    assert stored.label[0].text == original.label[0].text
    assert stored.name == original.name
    assert stored.iri == original.iri
    if len(original.description) == 0:
        assert stored.description == original.description
    else:
        assert stored.description[0].text == original.description[0].text
    assert stored.query_label == altered.query_label  # value == None -->
    # property not present and will be set (overwritten)
    assert stored.image == original.image
    assert stored.attachments == altered.attachments


def check_only_empty(
    original: model.Entity, altered: model.Entity, stored: model.Entity
):
    """Check the entity that was stored with the 'overwrite' param set to
    'only empty', which is supposed to overwrite only those properties of the
    entity in the OSW that are empty, but are not empty in the altered entity."""
    assert stored.label[0].text == original.label[0].text
    assert stored.name == original.name
    assert stored.iri == altered.iri
    assert stored.description[0].text == altered.description[0].text
    assert stored.query_label == altered.query_label
    assert stored.image == original.image
    assert stored.attachments == altered.attachments


def check_replace_remote(
    original: model.Entity, altered: model.Entity, stored: model.Entity
):
    """Check the entity that was stored with the 'overwrite' param set to
    'replace remote', which is supposed to replace the remote entity entirely."""
    assert stored.label[0].text == altered.label[0].text
    assert stored.name == altered.name
    assert stored.iri == altered.iri
    assert stored.description[0].text == altered.description[0].text
    assert stored.query_label == altered.query_label
    assert getattr(stored, "image", None) is None
    assert stored.attachments == altered.attachments


def check_keep_existing(
    original: model.Entity, altered: model.Entity, stored: model.Entity
):
    """Check the entity that was stored with the 'overwrite' param set to
    'keep existing', which is supposed to keep the existing entity in the OSW."""
    assert stored.label[0].text == original.label[0].text
    assert stored.name == original.name
    assert stored.iri == original.iri
    assert stored.description == original.description  # empty list
    assert stored.query_label == original.query_label
    assert stored.image == original.image
    assert getattr(stored, "attachments", None) is None


def test_apply_overwrite_policy():
    checks = [
        {  # Overwrite properties
            "overwrite": OverwriteOptions.true,
            "assert": check_true,
        },
        {  # Do not overwrite properties
            "overwrite": OverwriteOptions.false,
            "assert": check_false,
        },
        {  # Overwrite empty properties only
            "overwrite": OverwriteOptions.only_empty,
            "assert": check_only_empty,
        },
        {  # Replace the remote entity entirely
            "overwrite": AddOverwriteClassOptions.replace_remote,
            "assert": check_replace_remote,
        },
        {  # Keep the existing entity as is
            "overwrite": AddOverwriteClassOptions.keep_existing,
            "assert": check_keep_existing,
        },
    ]

    for check in checks:
        # Create a new item with some properties
        original_item = model.Item(
            label=[model.Label(text="My Item")],
            name="MyItem",
            iri="",  # Empty string property
            description=[],  # Empty list property
            query_label=None,  # Equal to a non-existing property
            image="File:OSWacacwdcawd.png",  # Property not in altered
        )
        original_page = OfflineWtPage(
            # wtSite=OSW.wt_site,  # todo: missing
            title="Item:"
            + OSW.get_osw_id(original_item.uuid)
        )
        original_page.set_slot_content(
            "jsondata", json.loads(original_item.json(exclude_none=True))
        )
        # Alter some of the property values
        altered_props = {
            "label": [model.Label(text="My Item Duplicate")],
            "name": "MyItemDuplicate",
            "iri": "http://example.com/MyItemDuplicate",
            "description": [model.Label(text="This is a duplicate")],
            "query_label": "My Item Duplicate",
            "attachments": ["File:OSWacacwdcawd.pdf"],  # Property not in original
        }
        # Create a new item with the altered properties
        original_props = {
            key: value
            for key, value in original_item.dict().items()
            if key in ["uuid", "type"]
        }
        altered_item = model.Item(**{**original_props, **altered_props})
        new_page = OSW._apply_overwrite_policy(
            param=OSW._ApplyOverwriteParam(
                page=original_page,
                entity=altered_item,
                policy=check["overwrite"],
                inplace=False,
            )
        )
        # Check the altered page
        new_content = new_page.get_slot_content("jsondata")
        new_item = model.Item(**new_content)

        check["assert"](original_item, altered_item, new_item)

        # todo: # where do we really eed to interact with an OSL isntance?
