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

        # todo: # where do we really need to interact with an OSL instance?


def test_wtpage_get_files():
    # Create an offline page with test content in slot main
    # Real-world example from Item:OSW8bccb1f0123f47d1831a1348ecbe63cc
    # (About this platform)
    page = OfflineWtPage()
    page.set_slot_content(
        "main",
        """

====File pages====
The following image gallery displays the relevant elements of a WikiFile page, which
 are specific to file pages.
{{Template:Viewer/Media
| image_size = 300
| mode = default
| textdata = File:OSW486215598a1f4993b063804775d70716.png{{!}}Example WikiFile page
with preview of the file;
File:OSWb4f81db0862d4430b45e6fcbda9fc1ff.PNG{{!}}Infobox of a WikiFile page;
File:OSWb6115f4d5b414a3f8b3dffd420c82c2e.PNG{{!}}Footer of a WikiFile page;
}}

===Semantic triples===
The semantic triple is the basic building block of semantic technology. It links two
nodes ("Subject" and "Object") by a "Property" (sometimes called "Predicate"), which
expresses the relation between the two, giving meaning to the link.
{{Template:Editor/DrawIO
| file_name = Semantic triple schematic
| page_name = Item:OSW8bccb1f0123f47d1831a1348ecbe63cc
| uuid = c4171917-ea09-4d98-823a-6af8282a6d50
| full_width = 0
| width = 300px
}}{{Template:Viewer/Media
| image_size = 600
| mode = default
| textdata = File:OSW51ad8f9d660641f9880006c40f41cb56.png{{!}}An example for a network
of semantic links, describing a publication, one of the authors and his affiliate;
}}

===Ontologies===
Ontologies aren't just vocabularies that define terms linke a dictionary would do.
Ontologies structure knowledge by defining concepts and the relations among them. Often,
they involve a hierarchy, which springs from a very generic object, aiming to describe
almost everything, like "Thing" in
{{Template:Viewer/Link|page=|url=https://schema.org/docs/full.html|label=Schema.org}}
or "Entity" within this [[:Category:Entity#Subcategories|platform]].
Use the > Symbol to expand different hierarchy levels and to explore the structure.

There are many ontologies in use and even more in development. Most scientific domains
have their own, often multiples. Here are some prominent examples:

*{{Template:Viewer/Link|page=|url=https://emmo-repo.github.io/|label=The Elementary
Multiperspective Material Ontology (EMMO)}}
* {{Template:Viewer/Link|page=|url=https://big-map.github.io/BattINFO/index.html|label=
Battery Interface Ontology (BattINFO)}}

==Object Orientation==
Object Orientation (OO) is a theoretical concept in computer science. It uses the
abstract concept of objects to describe and model real-world objects.

===Basic building blocks===
*Object


{{Template:Editor/DrawIO
| file_name = Basic building blocks of Object Orientation diagramm
| page_name = Item:OSW8bccb1f0123f47d1831a1348ecbe63cc
| uuid = 0bea84d5-4c07-4374-a4b4-5dc84d9ba302
| full_width = 0
| width = 200px
}}

===Linked Data===
Object oriented linked data (OO-LD) in Open Semantic Lab is our way to leverage the
functionality of linked data while employing concepts of object orientation to avoid
the redundant definition of (semantic) properties of objects and mapping of semantic
properties to ontologies.

The following figure sketches how Open Semantic Lab is used to modell objects in the
real-world. On the left we see a hierarchy of abstract concepts, starting from the most
generic at the top and ending up at the most specific at the bottom. At each level
either new properties are introduced or the range of property values is reduced to a
certain set to account for the specifics of a category. A category or class is used to
define and bundle all properties or attributes that items or instances of a certain
class have in common.  {{Template:Editor/DrawIO
| file_name = Object oriented linked data in OSL diagramm
| page_name = Item:OSW8bccb1f0123f47d1831a1348ecbe63cc
| uuid = 58baa09e-c00b-42cc-b077-9fe4d58ccf82
| width = 600px
}}

==Glossary of frequently used terms==
""",
    )

    file_list = page.find_file_page_refs_in_slots()
    print(file_list)
    assert len(file_list) == 7
    # assert if the file list contains the expected files
    assert "File:OSW486215598a1f4993b063804775d70716.png" in file_list
    assert "File:OSWb4f81db0862d4430b45e6fcbda9fc1ff.PNG" in file_list
    assert "File:OSWb6115f4d5b414a3f8b3dffd420c82c2e.PNG" in file_list
    assert "File:OSWc4171917ea094d98823a6af8282a6d50.drawio.svg" in file_list
    assert "File:OSW51ad8f9d660641f9880006c40f41cb56.png" in file_list
    assert "File:OSW0bea84d54c074374a4b45dc84d9ba302.drawio.svg" in file_list
    assert "File:OSW58baa09ec00b42ccb0779fe4d58ccf82.drawio.svg" in file_list
