"""Local file controller.

The implementation moved to ``opensemantic.core``, which owns the file models.
This subclass keeps the ``path`` argument and the filename-derived label of the
controller it replaces.
"""

import os
from pathlib import Path
from typing import IO, Any, Dict

from opensemantic.core.v1 import LocalFileController as _LocalFileController

from osw.core import model


class LocalFileController(_LocalFileController):
    """File controller for local files"""

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **kwargs):
        path = kwargs.pop("path", None)
        if path is not None and not kwargs.get("local_path"):
            kwargs["local_path"] = str(path)
        super().__init__(**kwargs)
        if not self.local_path:
            # The controller this replaces declared path as a required field,
            # so an instance without one never existed. Raising here keeps the
            # error at the call site that is wrong, instead of surfacing it on
            # the first read.
            raise ValueError(
                f"{type(self).__name__} needs a file: pass path= or local_path="
            )
        self._set_metadata()

    @classmethod
    def from_other(cls, other, path=None, **kwargs) -> "LocalFileController":
        if path is not None:
            kwargs["local_path"] = str(path)
        return other.cast(cls, **kwargs)

    def get(self) -> IO:
        self._set_metadata()
        return super().get()

    def put(self, file: IO, **kwargs: Dict[str, Any]):
        self._set_metadata()
        super().put(file, **kwargs)

    def _set_metadata(self):
        self.label = LocalFileController.extract_metadata(self.path).label

    @classmethod
    def extract_metadata(cls, path: Path) -> model.LocalFile:
        file = model.LocalFile(label=[model.Label(text=Path(path).name)])
        if os.path.exists(path):
            pass
            # stats = os.stat(path)
            # TODO: extract metadata
            # ... file.size = stats.st_size
        return file
