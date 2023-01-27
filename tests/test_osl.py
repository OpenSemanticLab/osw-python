from uuid import UUID

from osw.core import OSW


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
