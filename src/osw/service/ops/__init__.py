"""Operation implementations, one module per group.

Importing this package registers every operation in
:data:`osw.service.registry.REGISTRY`. Imports nothing from ``osw.mcp``,
``osw.cli``, the ``mcp`` SDK or ``typer``.
"""

from __future__ import annotations

from . import search
