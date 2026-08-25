"""Unit tests for osw.service.registry (Operation validation, bind()).

Registers test operations against a snapshot/restore of the global
``REGISTRY`` so this file cannot pollute other test modules. A fake
``osw``/``ledger`` is injected into ``Context`` so nothing here touches the
network.
"""

import inspect
from unittest.mock import MagicMock

import pytest

from osw.service import errors, registry
from osw.service.config import Settings
from osw.service.context import Context, Policy
from osw.service.ledger import LedgerRecord


@pytest.fixture(autouse=True)
def _clean_registry():
    original = dict(registry.REGISTRY)
    registry.REGISTRY.clear()
    yield
    registry.REGISTRY.clear()
    registry.REGISTRY.update(original)


def _settings() -> Settings:
    return Settings(domain="wiki.example.org", username="u", password="p")


def _underlying_message(exc_info) -> str:
    """Pydantic wraps our ``raise ValueError`` in its own message; unwrap it."""
    return str(exc_info.value.errors()[0]["ctx"]["error"])


def _valid_fn(ctx, title: str) -> dict:
    """Do a thing."""
    return {"title": title}


# -- Operation.command ------------------------------------------------------
def test_command_defaults_to_name():
    op = registry.Operation(name="foo", fn=_valid_fn)
    assert op.command == "foo"


def test_command_uses_cli_name_override():
    op = registry.Operation(name="foo", fn=_valid_fn, cli_name="bar")
    assert op.command == "bar"


# -- validator ----------------------------------------------------------
def test_validator_rejects_missing_ctx_param():
    def fn():
        """Doc."""
        return {}

    with pytest.raises(ValueError) as exc_info:
        registry.Operation(name="no_params", fn=fn)
    assert _underlying_message(exc_info).startswith("no_params:")


def test_validator_rejects_first_param_not_named_ctx():
    def fn(x):
        """Doc."""
        return {}

    with pytest.raises(ValueError) as exc_info:
        registry.Operation(name="bad_ctx", fn=fn)
    assert _underlying_message(exc_info).startswith("bad_ctx:")


def test_validator_rejects_records_without_writes():
    with pytest.raises(ValueError) as exc_info:
        registry.Operation(name="bad_records", fn=_valid_fn, records=lambda r: [])
    assert _underlying_message(exc_info).startswith("bad_records:")


def test_validator_requires_docstring():
    def fn(ctx, title: str) -> dict:
        return {}

    with pytest.raises(ValueError) as exc_info:
        registry.Operation(name="no_doc", fn=fn)
    assert _underlying_message(exc_info).startswith("no_doc:")


def test_validator_rejects_path_like_param_on_mcp_surface():
    def fn(ctx, source_path: str) -> dict:
        """Doc."""
        return {}

    with pytest.raises(ValueError) as exc_info:
        registry.Operation(name="bad_path", fn=fn)
    msg = _underlying_message(exc_info)
    assert msg.startswith("bad_path:")
    assert "source_path" in msg


def test_validator_allows_path_like_param_on_cli_only_surface():
    def fn(ctx, source_path: str) -> dict:
        """Doc."""
        return {}

    op = registry.Operation(name="cli_only", fn=fn, surfaces=frozenset({"cli"}))
    assert "source_path" in inspect.signature(op.fn).parameters


def test_extra_forbid_rejects_misspelled_kwarg():
    with pytest.raises(ValueError):
        registry.Operation(name="typo", fn=_valid_fn, sumary="oops")


# -- operation() decorator / REGISTRY ----------------------------------------
def test_operation_decorator_registers_and_returns_fn_unchanged():
    @registry.operation()
    def my_op(ctx, title: str) -> dict:
        """Do a thing."""
        return {"title": title}

    assert "my_op" in registry.REGISTRY
    assert registry.REGISTRY["my_op"].fn is my_op
    assert my_op(None, title="x") == {"title": "x"}


def test_operation_decorator_name_override():
    @registry.operation(name="custom_name")
    def my_op(ctx, title: str) -> dict:
        """Do a thing."""
        return {}

    assert "custom_name" in registry.REGISTRY
    assert "my_op" not in registry.REGISTRY


def test_operation_decorator_rejects_duplicate_name():
    @registry.operation()
    def dup(ctx, title: str) -> dict:
        """Do a thing."""
        return {}

    with pytest.raises(ValueError):

        @registry.operation(name="dup")
        def other(ctx, title: str) -> dict:
            """Do a thing."""
            return {}


# -- iter_operations ----------------------------------------------------
def _register(name, **kwargs):
    def fn(ctx, title: str) -> dict:
        """Do a thing."""
        return {"title": title}

    kwargs.setdefault("surfaces", frozenset({"mcp", "cli"}))
    registry.REGISTRY[name] = registry.Operation(name=name, fn=fn, **kwargs)


def test_iter_operations_filters_by_surface():
    _register("mcp_only", surfaces=frozenset({"mcp"}))
    _register("cli_only", surfaces=frozenset({"cli"}))
    names_mcp = {op.name for op in registry.iter_operations(surface="mcp")}
    names_cli = {op.name for op in registry.iter_operations(surface="cli")}
    assert "mcp_only" in names_mcp and "mcp_only" not in names_cli
    assert "cli_only" in names_cli and "cli_only" not in names_mcp


def test_iter_operations_filters_writes():
    _register("reader", writes=False)
    _register("writer", writes=True)
    with_writes = {op.name for op in registry.iter_operations(surface="mcp")}
    without_writes = {
        op.name for op in registry.iter_operations(surface="mcp", include_writes=False)
    }
    assert "writer" in with_writes
    assert "writer" not in without_writes
    assert "reader" in without_writes


def test_iter_operations_preserves_registration_order():
    _register("first")
    _register("second")
    _register("third")
    names = [op.name for op in registry.iter_operations(surface="mcp")]
    assert names.index("first") < names.index("second") < names.index("third")


# -- bind(): signature / annotations / doc preservation ----------------------
def test_bind_signature_excludes_ctx():
    def fn(ctx, title: str, limit: int = 5) -> dict:
        """Do a thing."""
        return {}

    op = registry.Operation(name="op1", fn=fn)
    ctx = Context(_settings(), osw=object())
    bound = registry.bind(op, ctx)

    sig = inspect.signature(bound)
    assert list(sig.parameters) == ["title", "limit"]
    assert "ctx" not in bound.__annotations__
    assert bound.__doc__ == fn.__doc__
    assert bound.__name__ == fn.__name__


# -- bind(): error handling --------------------------------------------------
def test_bind_errors_as_dicts_true_returns_payload():
    def fn(ctx, title: str) -> dict:
        """Do a thing."""
        raise errors.NotFound(f"Page '{title}' does not exist.")

    op = registry.Operation(name="op_err", fn=fn)
    ctx = Context(_settings(), Policy(errors_as_dicts=True), osw=object())
    bound = registry.bind(op, ctx)

    result = bound(title="Item:X")

    assert result == {"error": "Page 'Item:X' does not exist.", "type": "NotFound"}


def test_bind_errors_as_dicts_false_reraises():
    def fn(ctx, title: str) -> dict:
        """Do a thing."""
        raise errors.NotFound(f"Page '{title}' does not exist.")

    op = registry.Operation(name="op_err2", fn=fn)
    ctx = Context(_settings(), Policy(errors_as_dicts=False), osw=object())
    bound = registry.bind(op, ctx)

    with pytest.raises(errors.NotFound):
        bound(title="Item:X")


def test_bind_non_operror_exception_becomes_generic_dict():
    def fn(ctx, title: str) -> dict:
        """Do a thing."""
        raise RuntimeError("boom")

    op = registry.Operation(name="op_err3", fn=fn)
    ctx = Context(_settings(), Policy(errors_as_dicts=True), osw=object())
    bound = registry.bind(op, ctx)

    result = bound(title="x")

    assert result == {"error": "boom", "type": "RuntimeError"}


def test_bind_calls_require_write_for_writing_ops():
    def fn(ctx, title: str) -> dict:
        """Do a thing."""
        return {"title": title}

    op = registry.Operation(name="writer_op", fn=fn, writes=True)
    ctx = Context(
        _settings(),
        Policy(allow_writes=False, errors_as_dicts=True),
        osw=object(),
    )
    bound = registry.bind(op, ctx)

    result = bound(title="x")

    assert result["type"] == "ReadOnly"  # the ReadOnly OpError require_write raises


# -- bind(): ledger recording -------------------------------------------
def test_bind_invokes_ledger_once_per_returned_record_with_full_arguments():
    def fn(ctx, title: str) -> dict:
        """Do a thing."""
        return {"titles": [title, title + "-2"]}

    def _records(result: dict) -> list:
        return [
            LedgerRecord(
                title=result["titles"][0],
                op="create",
                change_id="c1",
                slots=["jsondata"],
            ),
            LedgerRecord(title=result["titles"][1], op="update", slots=["main"]),
        ]

    op = registry.Operation(
        name="writer_records",
        fn=fn,
        writes=True,
        records=_records,
    )
    fake_ledger = MagicMock()
    ctx = Context(_settings(), osw=object(), ledger=fake_ledger)
    bound = registry.bind(op, ctx)

    bound(title="Item:A")

    assert fake_ledger.record.call_count == 2

    first = fake_ledger.record.call_args_list[0]
    assert first.args == ("Item:A",)
    assert first.kwargs == {
        "tool": "writer_records",
        "op": "create",
        "change_id": "c1",
        "slots": ["jsondata"],
        "uuid": None,
        "namespace": None,
    }

    second = fake_ledger.record.call_args_list[1]
    assert second.args == ("Item:A-2",)
    assert second.kwargs == {
        "tool": "writer_records",
        "op": "update",
        "change_id": None,
        "slots": ["main"],
        "uuid": None,
        "namespace": None,
    }


def test_bind_does_not_invoke_ledger_when_op_does_not_write():
    def fn(ctx, title: str) -> dict:
        """Do a thing."""
        return {"titles": [title]}

    op = registry.Operation(name="reader_op", fn=fn, writes=False)
    fake_ledger = MagicMock()
    ctx = Context(_settings(), osw=object(), ledger=fake_ledger)
    bound = registry.bind(op, ctx)

    bound(title="Item:A")

    fake_ledger.record.assert_not_called()
