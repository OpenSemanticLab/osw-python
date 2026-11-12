"""In-memory file controller.

The implementation moved to ``opensemantic.core``, which owns the file models.
This module keeps the import path working.
"""

from opensemantic.core.v1 import InMemoryController

__all__ = ["InMemoryController"]
