import sys
from pathlib import Path

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.core import OSW, AddOverwriteClassOptions, OverwriteOptions
from osw.utils.wiki import get_full_title
from osw.wiki_tools import SearchParam
from osw.wtsite import WtSite

# run with: tox -e test -- --wiki_domain domain --wiki_username user --wiki_password pass


def test_store_and_load(wiki_domain, wiki_username, wiki_password):
    cm = CredentialManager()
    cm.add_credential(
        CredentialManager.UserPwdCredential(
            iri=wiki_domain, username=wiki_username, password=wiki_password
        )
    )
    wtsite = WtSite(WtSite.WtSiteConfig(iri=wiki_domain, cred_mngr=cm))
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
    # Make non-package scripts available for import
    cwd = Path(__file__).parent.absolute()
    tests_dir = cwd.parents[1] / "tests"
    sys.path.append(str(tests_dir))
    # Get required functions
    from tests.test_osl import (
        check_false,
        check_keep_existing,
        check_only_empty,
        check_replace_remote,
        check_true,
    )

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
            entity_title=OSW.LoadEntityParam(
                titles="Item:" + OSW.get_osw_id(original_item.uuid), disable_cache=True
            )
        ).entities[0]
        # Check the stored item
        check["assert"](original_item, altered_item, stored_item)
        # Delete the item
        osw.delete_entity(original_item)


def test_query_instances(wiki_domain, wiki_username, wiki_password):
    """Store an entity, query instances of the category of the entity, make sure the
    new entity is contained in the list of returned instances, delete the entity."""
    cm = CredentialManager()
    cm.add_credential(
        CredentialManager.UserPwdCredential(
            iri=wiki_domain, username=wiki_username, password=wiki_password
        )
    )
    wtsite = WtSite(WtSite.WtSiteConfig(iri=wiki_domain, cred_mngr=cm))
    osw = OSW(site=wtsite)
    # Create an item with a label
    my_item = model.Item(label=[model.Label(text="MyItem")])
    fpt = get_full_title(my_item)
    # Store the item in the OSW
    osw.store_entity(my_item)
    # Query instances of the category of the entity
    instances = osw.query_instances(
        category=OSW.QueryInstancesParam(categories="Category:Item", limit=10000)
    )
    assert fpt in instances
    # Delete the item
    osw.delete_entity(my_item)


def test_statement_creation(wiki_domain, wiki_username, wiki_password):
    cm = CredentialManager()
    cm.add_credential(
        CredentialManager.UserPwdCredential(
            iri=wiki_domain, username=wiki_username, password=wiki_password
        )
    )
    wtsite = WtSite(WtSite.WtSiteConfig(iri=wiki_domain, cred_mngr=cm))
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


def test_characteristic_creation(wiki_domain, wiki_username, wiki_password):
    cm = CredentialManager()
    cm.add_credential(
        CredentialManager.UserPwdCredential(
            iri=wiki_domain, username=wiki_username, password=wiki_password
        )
    )
    wtsite = WtSite(WtSite.WtSiteConfig(iri=wiki_domain, cred_mngr=cm))
    osw = OSW(site=wtsite)

    osw.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title=[
                "Category:OSWffe74f291d354037b318c422591c5023",  # CharacteristicType
                "Category:Property",
            ],
            mode="replace",
        )
    )

    # my_property = model.Property

    # Create a characteristic as instance of CharacteristicType
    my_characteristic = model.CharacteristicType(
        uuid="efad8086-4a76-47ca-b278-f5f944e5754b",
        name="TestCharacteristic",
        label=[model.Label(text="Test Characteristic")],
        properties=[
            model.PrimitiveProperty(
                uuid="766e7171-a183-4f9c-a9af-28cfd27fb1d9",
                name="test_property",
                type="string",
                property_type="SimpleProperty",
            ),
            model.PrimitiveProperty(
                uuid="766e7171-a183-4f9c-a9af-28cfd27fb1d1",
                name="test_property2",
                rdf_property="Property:TestPropertyWithSchema",
                property_type="SimpleProperty",
            ),
        ],
    )

    # store it as instance, which generates the schema
    # note: namespace and meta_category should be detected automatically in the future
    osw.store_entity(
        OSW.StoreEntityParam(
            entities=[my_characteristic],
            namespace="Category",
            meta_category_title="Category:OSWffe74f291d354037b318c422591c5023",
            overwrite=OverwriteOptions.true,
        )
    )

    pages = osw.site.get_page(
        WtSite.GetPageParam(titles=["Property:TestPropertyWithSchema"])
    ).pages
    pp = pages[0]
    # schema: dict = pp.get_slot_content("jsonschema")
    new_schema = {"type": "number", "description": "Imported from property schema"}
    pp.set_slot_content("jsonschema", new_schema)
    pp.edit()

    # load the characteristic as category
    osw.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title=[
                "Category:OSWefad80864a7647cab278f5f944e5754b"  # TestCharacteristic
            ],
            mode="append",
        )
    )

    # create an instance of the characteristic
    t = model.TestCharacteristic(test_property="Test", test_property2=1)
    assert t.test_property == "Test"
    assert t.test_property2 == 1

    # cleanup (disabled for paralle test matrix)
    # my_characteristic.meta = model.Meta(
    #     wiki_page=model.WikiPage(namespace="Category")
    # )  # namespace detection fails otherwise
    # osw.delete_entity(my_characteristic)
    # pp.delete()
