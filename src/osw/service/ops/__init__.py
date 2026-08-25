"""Operation implementations, one module per group.

Importing this package registers every operation in
:data:`osw.service.registry.REGISTRY`. Imports nothing from ``osw.mcp``,
``osw.cli``, the ``mcp`` SDK or ``typer``.

Import order fixes the order adapters see, so it is also the order tools are
registered on the MCP server and commands are listed in ``osw --help``.
"""

from __future__ import annotations

from . import entities, schema, search, slots, status
