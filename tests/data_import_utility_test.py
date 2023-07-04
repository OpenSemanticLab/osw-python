from uuid import UUID

from osw.core import OSW
from osw.data.import_utility import get_uuid_from_object_via_type


def get_uuid_from_object_via_type_test():
    expected = UUID("2ea5b605-c91f-4e5a-9559-3dff79fdd4a5")
    entity = {"type": "Item:" + OSW.get_osw_id(expected)}
    result = get_uuid_from_object_via_type(entity)
    assert result == expected
