import shutil
from io import StringIO
from typing import IO, Any, Dict, List, Optional

from osw.controller.file.base import FileController
from osw.core import model


class InMemoryController(FileController, model.LocalFile):
    """File controller for local files"""

    label: Optional[List[model.Label]] = [model.Label(text="Unnamed stream")]
    """the label of the stream, e.g., the name of the file the stream
    originates from. Defaults to 'Unnamed stream'."""
    stream: IO
    """the stream to the file"""

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **kwargs):
        self.stream = StringIO()
        super().__init__(**kwargs)

    def get(self) -> IO:
        return self.stream

    def put(self, file: IO, **kwargs: Dict[str, Any]):
        shutil.copyfileobj(file, self.stream)
