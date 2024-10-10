import os
import uuid

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.core import OSW
from osw.express import OswExpress
from osw.utils.wiki import get_full_title, get_uuid

# Credential manager(can use a file or hardcode the credentials, otherwise the user
#  will be prompted to enter them)
cm = CredentialManager(
    cred_filepath=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
    )
    # CredentialManager.UserPwdCredential(
    #     iri=wiki_domain, username=wiki_username, password=wiki_password
    # )
)
# Change the domain to your osw instance
osw_obj = OswExpress(domain="wiki-dev.open-semantic-lab.org", cred_mngr=cm)

# Load the required schemas / data classes
force_schema_reload = False
if force_schema_reload or not hasattr(
    model, "Corporation"
):  # only load if not already loaded. note: does not detect updated schemas yet
    DEPENDENCIES = {
        "MetaDeviceCategory": "Category:OSWd845b96813a344458f140e48c4d063fd",
        "Device(SubclassWithMetaModel)": "Category:OSW5bf1542d9cf847db83cbc73d579ba9d6",
        "Corporation": "Category:OSW5f4a3751d23e482d80fb0b72dcd6bc31",  #
    }
    osw_obj.install_dependencies(DEPENDENCIES, mode="replace")

# To reproduce your import you should define a UUIDv5 namespace
# Example: id of the source dataset / file
uuid_namespace = get_uuid("OSWc0dda5f5f066452dbab68cc8d5dcb022")

# Create a new manufacturer
new_manufacturer = model.Corporation(
    uuid=uuid.uuid5(
        uuid_namespace, "MyNewManufacturer"
    ),  # use a stable id from the source dataset / file
    name="MyNewManufacturer",
    label=[model.Label(text="My New Manufacturer", lang="en")],
    description=[model.Description(text="This is a test manufacturer", lang="en")],
)

# Create a new device type with the new manufacturer as manufacturer
new_category = model.MetaDeviceCategory(  # here used as a device type
    uuid=uuid.uuid5(
        uuid_namespace, "MyNewDeviceCategory"
    ),  # use a stable id from the source dataset / file
    subclass_of=[
        "Category:OSW5bf1542d9cf847db83cbc73d579ba9d6"
    ],  # Device (SubclassWithMetaModel)
    name="MyNewDeviceCategory",
    label=[model.Label(text="My New Category", lang="en")],
    description=[model.Description(text="This is a test device category", lang="en")],
    manufacturer=get_full_title(new_manufacturer),
)

# Store the manufacturer as an item
osw_obj.store_entity(OSW.StoreEntityParam(entities=[new_manufacturer]))
# Store the device type as a category. note: we have to request explicitly to create
#  a new category/class from this meta class instance
osw_obj.store_entity(
    OSW.StoreEntityParam(
        entities=[new_category],
        namespace="Category",
        # meta_category_title= (
        # "Category:OSWd845b96813a344458f140e48c4d063fd")
        # usage of MetaDeviceCategory not yet supported
    )
)

# Reload the schema (currently there is no direct way)
if force_schema_reload or not hasattr(
    model, "MyNewDeviceCategory"
):  # Only load if not already loaded. note: does not detect updated schemas yet
    osw_obj.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title=[
                get_full_title(new_category),  # MyNewDeviceCategory
            ],
            mode="append",
        )
    )

# Create a new device of the new device type
new_instance = model.MyNewDeviceCategory(
    uuid=uuid.uuid5(
        uuid_namespace, "MyNewDevice"
    ),  # use a stable id from the source dataset / file
    name="MyNewDevice",
    label=[model.Label(text="My New Device", lang="en")],
    description=[model.Description(text="This is a test device", lang="en")],
    serial_number="1234567890",
)

# Store the device instance as an item
osw_obj.store_entity(OSW.StoreEntityParam(entities=[new_instance]))
