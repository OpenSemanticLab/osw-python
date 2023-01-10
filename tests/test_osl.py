from uuid import UUID

from osw.osl import OSL


def test_osl_id_to_uuid():
    osl_id = "OSL2ea5b605c91f4e5a95593dff79fdd4a5"
    expected = UUID("2ea5b605-c91f-4e5a-9559-3dff79fdd4a5")
    result = OSL.get_uuid(osl_id)
    assert result == expected


def test_uuid_to_osl_id():
    uuid = UUID("2ea5b605-c91f-4e5a-9559-3dff79fdd4a5")
    expected = "OSL2ea5b605c91f4e5a95593dff79fdd4a5"
    result = OSL.get_osl_id(uuid)
    assert result == expected
