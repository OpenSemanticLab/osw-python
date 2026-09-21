"""Rendering helpers for the ``osw`` CLI.

Kept deliberately simple: this is not a table library, just enough structure
to make operation results readable on a terminal (or, with ``--json``,
machine-parseable).

The matching input-side helper, ``json_value``, lives in
:mod:`osw.service.params`: it is referenced from operation signatures, which
must not import an adapter.
"""

from __future__ import annotations

import json


def render(result: dict, *, as_json: bool) -> str:
    """Render an operation's result for the CLI.

    With ``as_json``, a plain ``json.dumps``. Otherwise a compact
    human-readable rendering: a ``{"titles": [...], "count": n, "truncated":
    bool}``-shaped result prints one title per line plus a count/truncation
    footer; any other dict renders as aligned ``key: value`` lines, with
    nested structures (dicts/lists) dumped as indented JSON.
    """
    if as_json:
        return json.dumps(result, indent=2, ensure_ascii=False)
    if _is_title_list(result):
        return _render_title_list(result)
    return _render_dict(result)


def _is_title_list(result: dict) -> bool:
    return (
        isinstance(result, dict)
        and isinstance(result.get("titles"), list)
        and "count" in result
    )


def _render_title_list(result: dict) -> str:
    lines = [str(title) for title in result["titles"]]
    count = result.get("count", len(result["titles"]))
    footer = f"{count} result{'s' if count != 1 else ''}"
    if result.get("truncated"):
        footer += " (truncated)"
    lines.append(footer)
    return "\n".join(lines)


def _render_dict(result: dict) -> str:
    if not isinstance(result, dict):
        return json.dumps(result, indent=2, ensure_ascii=False)
    width = max((len(str(key)) for key in result), default=0)
    lines = []
    for key, value in result.items():
        label = str(key).ljust(width)
        if isinstance(value, (dict, list)):
            nested = json.dumps(value, indent=2, ensure_ascii=False)
            indented = "\n".join(f"  {line}" for line in nested.splitlines())
            lines.append(f"{label}:\n{indented}")
        else:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)
