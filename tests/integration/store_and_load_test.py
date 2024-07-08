import mwclient

import osw.model.entity as model
from osw.core import OSW
from osw.wiki_tools import SearchParam
from osw.wtsite import WtSite

# run with: tox -e test -- --wiki_domain domain --wiki_username user --wiki_password pass


def test_store_and_load(wiki_domain, wiki_username, wiki_password):
    site = mwclient.Site(host=wiki_domain)
    site.login(username=wiki_username, password=wiki_password)
    wtsite = WtSite(WtSite.WtSiteLegacyConfig(site=site))
    osw = OSW(site=wtsite)
    # Check 1: Store an entity and download it again, delete afterward
    # Create an item with a label
    my_entity = model.Item(label=[model.Label(text="MyItem")])
    # Store the item in the OSW
    osw.store_entity(my_entity)
    # Load the item from the OSW
    my_entity2 = osw.load_entity("Item:" + OSW.get_osw_id(my_entity.uuid))
    # Check the stored item
    assert my_entity.label[0].text == my_entity2.label[0].text
    # Delete the item
    osw.delete_entity(my_entity)

    # Check 2: Store a more complex entity, create a local duplicate, with changed
    # properties, test the 'overwrite' param options, delete afterward
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

    def check_false(
        original: model.Entity, altered: model.Entity, stored: model.Entity
    ):
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

    checks = [
        {"overwrite": True, "assert": check_true},  # Overwrite properties
        {"overwrite": False, "assert": check_false},  # Do not overwrite properties
        {
            "overwrite": "only empty",  # Overwrite empty properties only
            "assert": check_only_empty,
        },
        {
            "overwrite": "replace remote",  # Replace the remote entity entirely
            "assert": check_replace_remote,
        },
        {
            "overwrite": "keep existing",  # Keep the existing entity as is
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
        print("Storing original entity...")
        osw.store_entity(original_item)
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
        # Update the item in the OSW
        print("Storing altered entity...")
        osw.store_entity(
            param=OSW.StoreEntityParam(
                entities=altered_item, overwrite=check["overwrite"]
            )
        )
        # Load the item from the OSW
        stored_item = osw.load_entity(
            entity_title=osw.LoadEntityParam(
                titles="Item:" + OSW.get_osw_id(original_item.uuid), disable_cache=True
            )
        ).entities[0]
        # Check the stored item
        check["assert"](original_item, altered_item, stored_item)
        # Delete the item
        osw.delete_entity(original_item)


def test_statement_creation(wiki_domain, wiki_username, wiki_password):
    site = mwclient.Site(host=wiki_domain)
    site.login(username=wiki_username, password=wiki_password)
    wtsite = WtSite(WtSite.WtSiteLegacyConfig(site=site))
    osw = OSW(site=wtsite)

    my_entity = model.Item(
        label=[model.Label(text="MyItem")],
        statements=[
            model.DataStatement(property="Property:TestProperty", value="TestValue")
        ],
    )

    osw.store_entity(my_entity)

    search_param = SearchParam(query="[[TestProperty::TestValue]]")
    full_page_titles = osw.site.semantic_search(search_param)
    assert f"Item:{OSW.get_osw_id(my_entity.uuid)}" in full_page_titles

    search_param = SearchParam(
        query="[[HasStatement.HasProperty::Property:TestProperty]]"
    )
    full_page_titles = osw.site.semantic_search(search_param)
    assert f"Item:{OSW.get_osw_id(my_entity.uuid)}" in full_page_titles

    osw.delete_entity(my_entity)
