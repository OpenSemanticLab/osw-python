"""File controllers.

Imported eagerly so the controllers register themselves: a caller that resolves
a file entity through the controller registry then finds the wiki
implementation without importing it by name.
"""

from osw.controller.file import base, local, memory, remote, wiki

__all__ = ["base", "local", "memory", "remote", "wiki"]
