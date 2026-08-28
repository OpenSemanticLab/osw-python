import shutil
from io import BytesIO
from typing import IO, Any, Dict, List, Optional

from pydantic.v1 import Field

from osw.controller.file.base import FileController
from osw.core import model


class InMemoryController(FileController, model.LocalFile):
    """File controller for in-memory streams"""

    label: Optional[List[model.Label]] = [model.Label(text="Unnamed stream")]
    """the label of the stream, e.g., the name of the file the stream
    originates from. Defaults to 'Unnamed stream'."""
    stream: Any = Field(default_factory=BytesIO)
    """the stream to the file, any file-like object. Defaults to an empty
    binary buffer. Byte-oriented, to match the get/put counterparts."""

    class Config:
        arbitrary_types_allowed = True

    def get(self) -> IO:
        return self.stream

    def put(self, file: IO, **kwargs: Dict[str, Any]):
        shutil.copyfileobj(file, self.stream)
