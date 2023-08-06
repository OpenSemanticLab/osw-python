from abc import abstractmethod
from typing import IO

from osw.core import model


class FileController(model.File):
    @abstractmethod
    def get(self) -> IO:
        pass

    @abstractmethod
    def put(self, file: IO):
        pass

    def put_from(self, other: "FileController"):
        with other.get() as f:
            self.put(f)

    def get_to(self, other: "FileController"):
        with self.get() as f:
            other.put(f)
