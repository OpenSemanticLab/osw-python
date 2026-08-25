"""Operation implementations, one module per group.

Importing this package registers every operation in
:data:`osw.service.registry.REGISTRY`. It imports nothing from ``osw.mcp``,
``osw.cli`` or the ``mcp`` SDK, so this package (and by extension
``osw.service``) stays importable without the optional ``mcp`` extra and never
depends on an adapter. ``typer`` is a base dependency, so op modules may import
it directly to mark up a parameter's CLI form (see ``create_or_update_entity``'s
``jsondata`` and :mod:`osw.service.params`); pydantic ignores ``Annotated``
metadata it does not recognise, so the MCP JSON schema is unaffected.

Import order fixes the order adapters see, so it is also the order tools are
registered on the MCP server and commands are listed in ``osw --help``.
"""

from __future__ import annotations

from . import entities, files, schema, search, slots, status
