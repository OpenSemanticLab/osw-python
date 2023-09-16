import os
import shutil
from io import TextIOBase
from pathlib import Path
from typing import IO, List, Optional

from osw.controller.file.base import FileController
from osw.core import model


class LocalFileController(FileController, model.LocalFile):
    """File controller for local files"""

    label: Optional[List[model.Label]] = [model.Label(text="Unnamed file")]
    """the label of the file, defaults to 'Unnamed file'"""
    path: Path
    """the path to the file"""

    @classmethod
    def from_other(cls, other: "FileController", path: Path) -> "LocalFileController":
        return other.cast(cls, path=path)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._set_metadata()

    class Config:
        arbitrary_types_allowed = True

    def get(self) -> IO:
        self._set_metadata()
        return open(self.path, "rb")

    def put(self, file: IO):
        self._set_metadata()
        mode = "wb"
        if isinstance(file, TextIOBase):
            mode = "w"
        with open(self.path, mode) as f:
            # f.write(file.read()) # in-memory - limited by available RAM
            shutil.copyfileobj(file, f)  # chunked copy

    def delete(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def _set_metadata(self):
        file = LocalFileController.extract_metadata(self.path)
        self.label = file.label

    @classmethod
    def extract_metadata(cls, path: Path) -> model.LocalFile:
        file = model.LocalFile(label=[model.Label(text=path.name)])
        if os.path.exists(path):
            pass
            # stats = os.stat(path)
            # TODO: extract metadata
            # ... file.size = stats.st_size
        return file
