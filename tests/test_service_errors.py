"""Unit tests for osw.service.errors.

Each ``OpError`` subclass must reproduce, key-for-key and value-for-value, the
error dict shape the MCP tools returned before the move to ``osw.service``.
"""

from osw.service import errors


def test_not_found_matches_export_entity_jsonld_shape():
    title = "Item:OSW1"
    exc = errors.NotFound(f"Entity '{title}' not found.")
    assert exc.payload() == {
        "error": f"Entity '{title}' not found.",
        "type": "NotFound",
    }
    assert exc.exit_code == 2


def test_not_found_matches_delete_entity_hybrid_shape():
    title = "Item:OSW1"
    exc = errors.NotFound(
        f"Page '{title}' does not exist.",
        extra={"title": title, "deleted": False},
    )
    assert exc.payload() == {
        "title": title,
        "deleted": False,
        "error": f"Page '{title}' does not exist.",
        "type": "NotFound",
    }


def test_external_delete_blocked_matches_delete_entity_shape():
    title = "Item:OSWx"
    message = (
        f"Refusing to delete '{title}': it was not created by this "
        "MCP server. Re-run with confirm_external_delete=true to override."
    )
    exc = errors.ExternalDeleteBlocked(message, extra={"title": title})
    assert exc.payload() == {
        "title": title,
        "error": message,
        "type": "ExternalDeleteBlocked",
    }
    assert exc.exit_code == 4


def test_schema_error_matches_create_or_update_entity_shape():
    exc = errors.SchemaError("boom1; boom2")
    assert exc.payload() == {"error": "boom1; boom2", "type": "SchemaError"}
    assert exc.exit_code == 3


def test_class_not_found_matches_create_or_update_entity_shape():
    category = "Category:Item"
    message = (
        f"Could not resolve a model class for '{category}' after "
        "fetching its schema. Check the category page name."
    )
    exc = errors.ClassNotFound(message)
    assert exc.payload() == {"error": message, "type": "ClassNotFound"}
    assert exc.exit_code == 3


def test_validation_error_matches_create_or_update_entity_shape():
    category = "Category:Item"
    message = f"jsondata does not validate against {category}: bad field"
    exc = errors.ValidationError(message)
    assert exc.payload() == {"error": message, "type": "ValidationError"}
    assert exc.exit_code == 3


def test_unknown_instance_matches_select_instance_shape():
    message = "Unknown instance 'bogus'. Available: wiki.example.org"
    exc = errors.UnknownInstance(message)
    assert exc.payload() == {"error": message, "type": "UnknownInstance"}
    assert exc.exit_code == 3


def test_not_configured_matches_sparql_query_shape():
    message = (
        "SPARQL endpoint not configured. Set OSW_SPARQL_ENDPOINT "
        "or pass the 'endpoint' argument."
    )
    exc = errors.NotConfigured(message)
    assert exc.payload() == {"error": message, "type": "NotConfigured"}
    assert exc.exit_code == 5


def test_invalid_slot_matches_slots_shape():
    valid = ["main", "jsondata"]
    message = f"Unknown slot 'bogus'. Valid slots: {valid}"
    exc = errors.InvalidSlot(message)
    assert exc.payload() == {"error": message, "type": "InvalidSlot"}
    assert exc.exit_code == 3


def test_invalid_content_matches_set_slot_shape():
    message = "Slot 'jsondata' is JSON; content must be an object or array."
    exc = errors.InvalidContent(message)
    assert exc.payload() == {"error": message, "type": "InvalidContent"}
    assert exc.exit_code == 3


def test_slot_missing_matches_set_slot_shape():
    message = (
        "Slot 'header' does not exist on 'Item:OSW1' and create_if_missing is false."
    )
    exc = errors.SlotMissing(message)
    assert exc.payload() == {"error": message, "type": "SlotMissing"}
    assert exc.exit_code == 3


def test_read_only_matches_require_write_shape():
    message = (
        "Operation 'create_or_update_entity' is not permitted: writes are "
        "disabled (set OSW_READ_ONLY=false to allow)."
    )
    exc = errors.ReadOnly(message)
    assert exc.payload() == {"error": message, "type": "ReadOnly"}
    assert exc.exit_code == 4


def test_base_op_error_defaults():
    exc = errors.OpError("generic failure")
    assert exc.payload() == {"error": "generic failure", "type": "Error"}
    assert exc.exit_code == 1
