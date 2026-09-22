"""Version banner shared by the osw CLI and the osw-mcp server.

Neither adapter may import the other (see :mod:`osw.service.streams`), so the
one line both ``--version`` options print lives here instead of in either of
them. See :func:`version_line`.
"""

from __future__ import annotations

import os
import platform

import osw


def version_line(prog: str) -> str:
    """The one-line version banner ``prog`` prints for --version / -V.

    ``prog`` names the console script asking (``"osw"`` or ``"osw-mcp"``), so
    the same installed package reports under whichever command the caller
    actually ran. The remaining fields are the installed osw version, the
    directory the osw package was loaded from, and the running Python
    version, in that order.
    """
    location = os.path.dirname(osw.__file__)
    return (
        f"{prog} {osw.__version__} from {location} (Python {platform.python_version()})"
    )
