"""Unit tests for the osw.mcp provenance ledger."""

from osw.mcp.ledger import Ledger


def _ledger(tmp_path):
    return Ledger(domain="wiki.example.org", state_dir=str(tmp_path))


def test_record_and_is_tracked(tmp_path):
    ledger = _ledger(tmp_path)
    assert ledger.is_tracked("Item:OSW1") is False
    ledger.record("Item:OSW1", op="create", tool="create_or_update_entity")
    assert ledger.is_tracked("Item:OSW1") is True
    assert ledger.path.is_file()


def test_mark_deleted_untracks(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record("Item:OSW1", op="create", tool="create_or_update_entity")
    ledger.mark_deleted("Item:OSW1")
    assert ledger.is_tracked("Item:OSW1") is False


def test_record_merges_and_dedups(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record(
        "Item:OSW1",
        op="create",
        tool="create_or_update_entity",
        change_id="c1",
        slots=["jsondata"],
    )
    ledger.record(
        "Item:OSW1",
        op="update",
        tool="set_slot",
        change_id="c1",
        slots=["main", "jsondata"],
    )
    data = ledger._load()["entries"]["Item:OSW1"]
    assert data["ops"] == ["create", "update"]
    assert data["tools"] == ["create_or_update_entity", "set_slot"]
    assert data["change_ids"] == ["c1"]  # deduped
    assert sorted(data["slots_written"]) == ["jsondata", "main"]  # deduped


def test_recreate_after_delete_retracks(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record("Item:OSW1", op="create", tool="create_or_update_entity")
    ledger.mark_deleted("Item:OSW1")
    assert ledger.is_tracked("Item:OSW1") is False
    ledger.record("Item:OSW1", op="create", tool="create_or_update_entity")
    assert ledger.is_tracked("Item:OSW1") is True


def test_entry_count_excludes_deleted(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record("Item:OSW1", op="create", tool="t")
    ledger.record("Item:OSW2", op="create", tool="t")
    ledger.mark_deleted("Item:OSW1")
    assert ledger.entry_count() == 1


def test_corrupt_ledger_starts_fresh(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.path.parent.mkdir(parents=True, exist_ok=True)
    ledger.path.write_text("{not valid json", encoding="utf-8")
    # is_tracked must not raise on a corrupt file
    assert ledger.is_tracked("Item:OSW1") is False
    ledger.record("Item:OSW1", op="create", tool="t")
    assert ledger.is_tracked("Item:OSW1") is True


def test_persistence_across_instances(tmp_path):
    _ledger(tmp_path).record("Item:OSW1", op="create", tool="t")
    # a fresh Ledger over the same dir sees the persisted entry
    assert _ledger(tmp_path).is_tracked("Item:OSW1") is True
