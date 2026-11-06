"""osw: a command-line client assembled from the same ``osw.service.registry``
that ``osw-mcp`` uses.

Every operation is registered once (see :mod:`osw.service.ops`) and exposed
identically by every adapter; this package's only job is to turn that
registry into a ``typer`` command tree.
"""

from __future__ import annotations
