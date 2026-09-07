"""Operation registry: one decorated function exposed identically by every
osw.service adapter (MCP, CLI, ...).

An :class:`Operation` pairs a plain function -- whose first parameter is a
:class:`~osw.service.context.Context` and whose remaining parameters are its
public parameter surface -- with the metadata each adapter needs (MCP tool
annotations, CLI grouping, ledger recording). Adding an operation means
writing one decorated function; no adapter needs editing.

This module imports nothing from the ``mcp`` SDK, ``typer``, or ``osw.cli``.
"""

from __future__ import annotations

import inspect
import sys
from typing import Any, Callable, Iterator, Literal, Optional, get_type_hints

from pydantic import BaseModel, ConfigDict, Field, model_validator

from osw.service.context import Context
from osw.service.errors import OpError
from osw.service.ledger import LedgerRecord

PATH_LIKE_NAMES = frozenset({
    "path",
    "paths",
    "filepath",
    "file_path",
    "dir",
    "directory",
    "target_dir",
    "target_path",
    "source_path",
    "dest",
    "destination",
    "output_path",
    "outfile",
    "local_path",
})


class Operation(BaseModel):
    """One osw operation, exposed identically by every adapter.

    ``fn``'s first parameter is a Context; its remaining parameters *are* the
    public parameter surface. The MCP SDK derives its JSON schema from them and
    typer derives its CLI options from them, so adding an operation means
    writing one decorated function and editing no adapter.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    name: str
    fn: Callable[..., dict]
    group: Optional[str] = None  # CLI first level, e.g. "entity"
    cli_name: Optional[str] = None  # CLI second level; defaults to name
    summary: str = ""
    writes: bool = False
    surfaces: frozenset[Literal["mcp", "cli"]] = frozenset({"mcp", "cli"})
    # ledger hook: given the fn's result, returns the entries to record after
    # a successful write. ``tool`` is not part of ``LedgerRecord``; ``bind()``
    # fills it in from the operation name.
    records: Optional[Callable[[dict], list[LedgerRecord]]] = None

    # MCP tool annotations: the spec's four hints, explicit and typed rather
    # than a dict. The adapter maps these onto ToolAnnotations, so this
    # module still imports nothing from the mcp SDK.
    read_only_hint: Optional[bool] = None
    destructive_hint: Optional[bool] = None
    idempotent_hint: Optional[bool] = None
    open_world_hint: Optional[bool] = None

    # MCP _meta: open-ended by spec, so the two keys we use are typed and
    # anything else goes through the escape hatch.
    requires_user_interaction: bool = False
    max_result_size_chars: Optional[int] = None
    extra_meta: dict[str, Any] = Field(default_factory=dict)

    @property
    def command(self) -> str:
        """The CLI second-level command name."""
        return self.cli_name or self.name

    @model_validator(mode="after")
    def _validate(self) -> Operation:
        params = list(inspect.signature(self.fn).parameters.values())
        if not params:
            raise ValueError(f"{self.name}: fn must take at least one parameter (ctx).")
        if params[0].name != "ctx":
            raise ValueError(
                f"{self.name}: fn's first parameter must be named 'ctx', got "
                f"{params[0].name!r}."
            )
        if self.records is not None and not self.writes:
            raise ValueError(
                f"{self.name}: records is set but writes is False; it would never fire."
            )
        if not (self.fn.__doc__ and self.fn.__doc__.strip()):
            raise ValueError(
                f"{self.name}: fn must have a non-empty docstring; it becomes "
                "the MCP tool description and the CLI help."
            )
        if "mcp" in self.surfaces:
            offending = [p.name for p in params[1:] if p.name in PATH_LIKE_NAMES]
            if offending:
                raise ValueError(
                    f"{self.name}: parameter(s) {', '.join(offending)} look "
                    "like filesystem paths and may not be exposed on the mcp "
                    "surface; no path may reach an MCP client."
                )
        return self


REGISTRY: dict[str, Operation] = {}


def operation(**kwargs: Any) -> Callable[[Callable[..., dict]], Callable[..., dict]]:
    """Decorate ``fn`` as an :class:`Operation`, registering it in :data:`REGISTRY`.

    Returns ``fn`` unchanged so it stays directly callable and unit-testable.
    """

    def deco(fn: Callable[..., dict]) -> Callable[..., dict]:
        name = kwargs.get("name") or fn.__name__
        if name in REGISTRY:
            raise ValueError(
                f"{name}: an operation with this name is already registered."
            )
        fields = {**kwargs, "name": name, "fn": fn}
        REGISTRY[name] = Operation(**fields)
        return fn

    return deco


def iter_operations(
    *, surface: str, include_writes: bool = True
) -> Iterator[Operation]:
    """Yield registered operations available on ``surface``, in registration order."""
    for op in REGISTRY.values():
        if surface not in op.surfaces:
            continue
        if op.writes and not include_writes:
            continue
        yield op


def bind(op: Operation, ctx: Context) -> Callable[..., dict]:
    """Apply ``ctx`` to ``op.fn`` and hide it from the resulting signature."""

    def bound(*args: Any, **kwargs: Any) -> dict:
        try:
            if op.writes:
                ctx.require_write(op.name)
            with ctx.guard():
                result = op.fn(ctx, *args, **kwargs)
                if op.writes and op.records is not None:
                    for rec in op.records(result):
                        ctx.ledger.record(
                            rec.title, tool=op.name, **rec.model_dump(exclude={"title"})
                        )
            return result
        except Exception as exc:
            if not ctx.policy.errors_as_dicts:
                raise
            print(f"[osw] {op.name} failed: {exc!r}", file=sys.stderr)
            if isinstance(exc, OpError):
                return exc.payload()
            return {"error": str(exc), "type": type(exc).__name__}

    # Resolve annotations here, against the op module's globals. `bound` lives in
    # this module, so a consumer calling get_type_hints() on it would otherwise
    # try to resolve `from __future__ import annotations` strings against the
    # wrong namespace. include_extras keeps Annotated[...] metadata intact.
    try:
        hints = get_type_hints(op.fn, include_extras=True)
    except Exception:  # unresolvable forward ref: leave the strings in place
        hints = {}

    sig = inspect.signature(op.fn)
    params = [
        p.replace(annotation=hints.get(p.name, p.annotation))
        for p in list(sig.parameters.values())[1:]  # drop ctx
    ]
    annotations = dict(getattr(op.fn, "__annotations__", {}))
    annotations.update(hints)
    annotations.pop("ctx", None)

    bound.__name__ = op.fn.__name__
    bound.__qualname__ = op.fn.__qualname__
    bound.__doc__ = op.fn.__doc__
    bound.__signature__ = sig.replace(
        parameters=params,
        return_annotation=hints.get("return", sig.return_annotation),
    )
    bound.__annotations__ = annotations
    return bound
