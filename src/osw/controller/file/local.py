import os
import shutil
from pathlib import Path
from typing import IO, Optional

from osw.controller.file.file import FileController
from osw.core import model


class LocalFileController(FileController, model.LocalFile):
    path: Optional[Path]
    file: Optional[IO]

    class Config:
        arbitrary_types_allowed = True

    def get(self) -> IO:
        # with open(self.path, "r") as f:
        #    self.file = f.read()
        self.file = open(self.path, "rb")
        return self.file

    def put(self, file: IO):
        with open(self.path, "wb") as f:
            # f.write(file.read())
            shutil.copyfileobj(file, f)  # chunked copy

    def delete(self):
        if os.path.exists(self.path):
            os.remove(self.path)
