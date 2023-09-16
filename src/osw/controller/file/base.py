from abc import abstractmethod
from typing import IO, Any

from osw.core import model


class FileController(model.File):
    """Base class for file controllers"""

    @abstractmethod
    def get(self) -> IO:
        """Reads or downloads a file from an IO object
        Make sure to close the IO object after reading

        Returns
        -------
            the IO object of the opened file
        """
        pass

    @abstractmethod
    def put(self, file: IO):
        """Writes or uploads a file from an IO object

        Parameters
        -------
            file
                the IO object to read from
        """
        pass

    def put_from(self, other: "FileController"):
        """Writes or uploads a file from another file controller
        Automatically closes the other file controllers IO object after reading

        Parameters
        ----------
        other
            another file controller to read from
        """
        with other.get() as f:
            self.put(f)

    def get_to(self, other: "FileController"):
        """Reads or downloads a file to another file controller
        Automatically closes the this file controllers IO object after reading

        Parameters
        ----------
        other
            another file controller to write to
        """
        with self.get() as f:
            other.put(f)

    @classmethod
    def from_other(cls, other: "FileController", **kwargs: Any) -> "FileController":
        """Create an instance based on another file controller
        copying all common attributes

        Parameters
        ----------
        other
            another file controller to copy from
        kwargs
            additional attributes to be set
        """
        return other.cast(cls, **kwargs)
