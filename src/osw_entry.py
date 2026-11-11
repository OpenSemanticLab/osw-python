"""Console-script shims for the ``osw`` and ``osw-mcp`` entry points.

Importing :mod:`osw` writes a one-off notice to the ``osw`` logger, unless
``OSW_LOG_LEVEL`` is already set in the environment (see
``src/osw/__init__.py``). That notice is meant for library users, who are
told where osw's logging lives and how to change it. For the two console
scripts, osw is the application rather than a library, so the notice is
clutter, and this module sets the environment variable before osw is
imported to suppress it. Nothing inside the osw package can do this itself:
importing any of its submodules imports the package first, and the notice
has already been written by the time control reaches that submodule. So the
suppression has to happen here, outside the osw package, before osw enters
the picture at all.
"""

from __future__ import annotations

import os

#: The level the shim sets. It is the name of osw's own DEFAULT_LOG_LEVEL,
#: written out rather than imported, because importing osw here would emit
#: the very notice this module exists to suppress. A test in
#: tests/test_osw_entry.py keeps the two in step.
_DEFAULT_LEVEL = "INFO"


def _suppress_import_notice():
    """Sets OSW_LOG_LEVEL before osw is imported, so its notice stays quiet

    Uses setdefault so a value the caller already set is left alone. The
    value chosen is osw's own DEFAULT_LOG_LEVEL, so the log level stays
    exactly what it is today; only the notice about it disappears.
    """
    os.environ.setdefault("OSW_LOG_LEVEL", _DEFAULT_LEVEL)


def cli():
    _suppress_import_notice()
    # Imported here, not at module level: a module-level import would run
    # osw/__init__.py before _suppress_import_notice() had a chance to set
    # the environment variable.
    from osw.cli.main import app

    app()


def mcp():
    _suppress_import_notice()
    # Imported here, not at module level, for the same reason as in cli()
    # above: osw/__init__.py must not run before the variable is set.
    from osw.mcp.server import main

    main()
