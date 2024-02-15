from pathlib import Path
from typing import Union


class BufferedPrint:
    """A class that buffers print messages and prints them all at once when flush is
    called.

    Examples
    --------
    # Create a BufferedPrint object
    >>> message_buffer = BufferedPrint()
    # Redirect print to the BufferedPrint object
    >>> print("Some message", file=message_buffer)
    # Flush the buffered messages and print them
    >>> message_buffer.flush()
    """

    def __init__(self):
        self.messages = []

    def write(self, message):
        self.messages.append(message)

    def flush(self):
        # Process the buffered messages
        for message in self.messages:
            print(message, end="")

        # Clear the buffered messages
        self.messages = []


def list_files_and_directories(
    search_path: Union[str, Path], recursive: bool = True
) -> dict[str, list[Path]]:
    """List files and subdirectories in the specified path. Return them as list
    nested in a directory.

    Parameters
    ----------
    search_path:
        The path to the directory.
    recursive:
        If True, the function will recursively search for files and directories.

    Returns
    -------
    result:
        A dictionary with a list each of files and directories in the directory.
    """
    search_path = Path(search_path)

    if not search_path.is_dir():
        raise ValueError(f"{search_path} is not a directory.")

    files = []
    directories = []

    for item in search_path.iterdir():
        if item.is_file():
            files.append(item)
        elif item.is_dir():
            directories.append(item)
            if recursive:
                ret_val = list_files_and_directories(item, recursive=True)
                files.extend(ret_val["files"])
                directories.extend(ret_val["directories"])

    return {"directories": directories, "files": files}


def file_in_paths(
    paths: list[Union[str, Path]], file_name: Union[str, Path]
) -> dict[str, Union[bool, Path]]:
    result = False
    path = None
    for path in paths:
        if path.name == file_name:
            result = True
            break
    return {"found": result, "file path": path}
