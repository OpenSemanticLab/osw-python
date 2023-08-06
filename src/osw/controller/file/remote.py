from abc import abstractmethod
from typing import IO

from osw.controller.file.file import FileController
from osw.core import model


# note: the order of the base classes is important
# the data class must be the first base class, otherwise subclass controllers fall back to the data model of the controller superclass
class RemoteFileController(model.RemoteFile, FileController):
    @abstractmethod
    def get() -> IO:
        pass

    @abstractmethod
    def put(file: IO):
        pass

    # @classmethod
    # def from_local(self, local: "local.LocalFileController") -> "RemoteFileController":
    #    rf = local.cast(self)
    #    rf.put(local.get())
    #    return rf

    # def from_local(self, local: "local.LocalFileController") -> None:
    #    with local.get() as f:
    #        self.put(f)
