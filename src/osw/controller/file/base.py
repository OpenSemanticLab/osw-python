"""File controller interface.

The implementation moved to ``opensemantic.core``, which owns the file models.
This module keeps the import path working.
"""

from opensemantic.core.v1 import FileControllerMixin as FileController

__all__ = ["FileController"]
