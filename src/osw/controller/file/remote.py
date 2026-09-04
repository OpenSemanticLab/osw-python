from abc import abstractmethod
from typing import IO, Any, Dict

from osw.controller.file.base import FileController
from osw.core import model

# TODO: add additional remove file with
#  https://docs.prefect.io/2.11.4/concepts/filesystems/


# Note: the order of the base classes is important
# The data class must be the first base class, otherwise subclass controllers fall back
#  to the data model of the controller superclass
class RemoteFileController(model.RemoteFile, FileController):
    @property
    def uri(self) -> str:
        """The url the file is stored at, e.g., 's3://' for S3FileController and
        'https://' for WikiFileController

        A remote controller keeps its location in 'url', either as a field of its
        data model, as model.S3File does, or as a property, as WikiFileController
        does. model.RemoteFile does not declare it, so this is a contract between
        the subclasses rather than something the base class can enforce."""
        return self.url

    @abstractmethod
    def get(self) -> IO:
        pass

    @abstractmethod
    def put(self, file: IO, **kwargs: Dict[str, Any]):
        pass

    # @classmethod
    # def from_local(self, local: "local.LocalFileController") -> "RemoteFileController":
    #    rf = local.cast(self)
    #    rf.put(local.get())
    #    return rf

    # def from_local(self, local: "local.LocalFileController") -> None:
    #    with local.get() as f:
    #        self.put(f)
