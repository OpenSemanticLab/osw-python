"""Remote file controller.

The implementation moved to ``opensemantic.core``, which owns the file models.
This module keeps the import path working.
"""

from opensemantic.core.v1 import RemoteFileController

__all__ = ["RemoteFileController"]
