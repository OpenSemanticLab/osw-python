"""Parsers for operation parameters whose CLI form differs from their Python type.

An operation declares its parameter surface once, so a parameter typed ``dict``
needs a way to say how a shell should spell it. typer reads that from
``Annotated[..., typer.Option(parser=...)]`` metadata on the parameter, and
pydantic ignores metadata it does not recognise, so attaching a parser here
leaves the MCP JSON schema untouched.

This module lives in ``osw.service`` rather than ``osw.cli`` so the dependency
runs adapter -> core: an op module must never import an adapter. typer is a base
dependency, so importing it here costs nothing extra. ``typer.BadParameter`` is
used deliberately -- click discards the message of a plain ``ValueError`` raised
from a ``parser=`` callback and reports only the offending value.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer


def json_value(raw: str) -> Any:
    """Typer parser for structured (JSON) CLI parameters.

    Accepts a JSON literal, ``@path/to/file.json`` (read the file's
    contents), or ``-`` (read from stdin).
    """
    if raw == "-":
        source = "stdin"
        text = sys.stdin.read()
    elif raw.startswith("@"):
        path = raw[1:]
        source = path
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise typer.BadParameter(f"Could not read '{path}': {exc}")
    else:
        source = "argument"
        text = raw

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON ({source}): {exc}")
