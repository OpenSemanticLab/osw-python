import os
import shutil
from pathlib import Path
from typing import IO, Optional

from osw.controller.file.base import FileController
from osw.core import model


class LocalFileController(FileController, model.LocalFile):
    label: Optional[model.Label] = model.Label(text="Unnamed file")
    path: Path

    class Config:
        arbitrary_types_allowed = True

    def get(self) -> IO:
        self._set_metadata()
        return open(self.path, "rb")

    def put(self, file: IO):
        self._set_metadata()
        with open(self.path, "wb") as f:
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
