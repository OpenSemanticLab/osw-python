import asyncio
import sys
from asyncio import Queue
from contextlib import redirect_stdout, suppress
from io import StringIO  # , BytesIO,

# import stdio_proxy
from pathlib import Path
from typing import IO, Callable, Iterable, Optional, Union

import dask
from dask.diagnostics import ProgressBar

# dask.config.set(scheduler="threads")
# with stdio_proxy.redirect_stdout(sys.stdout):
# "processes" scheduler leads to no messages ending up in the buffer / no flushing
# "threads" scheduler leads to all messages being printed immediatley without buffering
# with contextlib.redirect_stdout(sys.stdout):
# "processes" scheduler leads to no messages ending up in the buffer / no flushing
# "threads" scheduler leads to all buffered messages as expected


class MessageBuffer:
    """A class that buffers print messages and prints them all at once when
    flush is called. Can also be used as a context manager.

    Examples
    --------
    # Regular usage:
    # Create a BufferedPrint object
    >>> buffer = MessageBuffer()
    # Redirect print to the BufferedPrint object
    >>> print("Some message", file=buffer)
    # Flush the buffered messages and print them
    >>> buffer.flush()
    # As context manager:
    >>> with MessageBuffer() as buffer:
    ...     print("Some message", file=buffer)
    """

    def __init__(self, debug: bool = True):
        self.debug = debug
        self.messages = []
        self.closed = False  # Always open

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.debug:
            self.flush()
        self.closed = True

    def write(self, message):
        self.messages.append(message)

    def flush(self):
        # Process the buffered messages
        for message in self.messages:
            print(message, end="", file=sys.stdout)
        self.messages = []


class AsyncMessageBuffer(MessageBuffer):
    """Work in progress.


    A class that buffers print messages and prints them all at once when
    flush is called. Can also be used as a context manager.

    Examples
    --------
    # Regular usage:
    # Create a BufferedPrint object
    >>> buffer = MessageBuffer()
    # Redirect print to the BufferedPrint object
    >>> print("Some message", file=buffer)
    # Flush the buffered messages and print them
    >>> buffer.flush()
    # As context manager:
    >>> with MessageBuffer() as buffer:
    ...     print("Some message", file=buffer)
    """

    def __init__(self, debug: bool = True):
        super().__init__(debug=debug)
        self.messages = Queue()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.debug:
            self.flush()
        self.closed = True

    def write(self, message):
        self.messages.put(message)

    def flush(self):
        # Process the buffered messages
        while not self.messages.empty():
            message = self.messages.get()
            print(message, end="", file=sys.stdout)


def redirect_print(
    file_like: Union[IO, Path, MessageBuffer, AsyncMessageBuffer]
) -> Callable:
    def decorator(func_: Callable) -> Callable:
        """

        Parameters
        ----------
        func_:
            The function to decorate.

        Returns
        -------
        wrapper:
            The wrapped function.
        """

        def wrapper(*args, **kwargs):
            # First redirect stdout to a buffer
            with StringIO() as buf, redirect_stdout(buf):
                # with BytesIO() as buf, stdio_proxy.redirect_stdout(buf):
                return_val = func_(*args, **kwargs)
                output = buf.getvalue()
            # Reset stdout to the original value
            with suppress(AttributeError):
                # sys.stdout.close()
                sys.stdout = sys.__stdout__
                if sys.stdout.closed:
                    raise ValueError("sys.stdout is closed.")
            lines = output.splitlines()
            if getattr(file_like, "closed", None):
                raise ValueError(
                    "File or buffer is closed. Open prior to "
                    "execution of the decorated function."
                )
            if isinstance(file_like, Path) or isinstance(file_like, str):
                path = Path(file_like)
                if not path.exists():
                    raise FileNotFoundError(f"File {path} does not exist.")
                file_buffer = path.open("w")
                try:
                    for line in lines:
                        print(line, file=file_buffer)
                finally:
                    file_buffer.close()
            else:
                for line in lines:
                    print(line, file=file_like)

            return return_val

        return wrapper

    return decorator


def redirect_print_explicitly(
    func: Optional[Callable] = None,
    file_like: Optional[Union[IO, Path, MessageBuffer, AsyncMessageBuffer]] = None,
    line_print: Optional[Callable] = None,
) -> Callable:
    """A decorator that redirects print messages to a file or buffer and optionally
    applies a line_print function to each line. If line_print is not None, the print


    Parameters
    ----------
    func:
        The function to decorate.
    file_like:
        The file or buffer to redirect the print messages to.
    line_print:
        A function that will be called for each line of the print message.

    Returns
    -------
    Depending on usage, the decorated function or the decorator.

    Source
    ------
    Adapted from: https://bytepawn.com/python-decorators-for-data-scientists.html

    """
    # Code here is executed at decoration - when the decorator is used
    def decorator(func_: Callable, **kwargs) -> Callable:
        """

        Parameters
        ----------
        func_:
            The function to decorate.

        Returns
        -------
        wrapper:
            The wrapped function.
        """

        def wrapper(*args_, **kwargs_):
            kwargs_.update(kwargs)
            # First redirect stdout to a buffer
            with StringIO() as buf, redirect_stdout(buf):
                # with BytesIO() as buf, stdio_proxy.redirect_stdout(buf):
                return_val = func_(*args_, **kwargs_)
                output = buf.getvalue()
            # Reset stdout to the original value
            with suppress(AttributeError):
                # sys.stdout.close()
                sys.stdout = sys.__stdout__
                if sys.stdout.closed:
                    raise ValueError("sys.stdout is closed.")
            lines = output.splitlines()
            if line_print is not None:
                lines = [
                    line_print(line) for line in lines if line_print(line) is not None
                ]

            if getattr(file_like, "closed", None):
                raise ValueError(
                    "File or buffer is closed. Open prior to "
                    "execution of the decorated function."
                )
            if isinstance(file_like, Path) or isinstance(file_like, str):
                path = Path(file_like)
                if not path.exists():
                    raise FileNotFoundError(f"File {path} does not exist.")
                file_buffer = path.open("w")
                try:
                    for line in lines:
                        print(line, file=file_buffer)
                finally:
                    file_buffer.close()
            elif file_like is None:
                # todo: fix - does not store the messages until parallel execution
                #  finishes
                # Maybe because this code is only executed at the call of the wrapped
                # function and therefore, the buffer object is not shared between tasks
                buffer = MessageBuffer()
                for line in lines:
                    print(line, file=buffer)
                print("Printing buffered messages.")
                buffer.flush()
            else:
                for line in lines:
                    print(line, file=file_like)
                    # it seems that this write-operation is sometimes redirected in
                    # parallel execution as if print(line, file=None) was used

            return return_val

        return wrapper

    # Code here is executed at decoration - when the decorator is used
    if func is None:
        # decorator was used like @redirect(...)
        return decorator
    else:
        # decorator was used like @redirect, without parens
        return decorator(func_=func)


def parallelize(
    func: Callable,
    iterable: Iterable,
    flush_at_end: bool = False,
    progress_bar: bool = True,
    **kwargs,
):
    """A function to parallelize tasks with a progress bar and a message buffer.

    Parameters
    ----------
    func:
        The function to be executed in parallel.
    iterable:
        The iterable, who's items are to be passed as singles to the function.
    flush_at_end:
        If True, the message buffer will be printed (flushed) to stdout after parallel
        execution.
    progress_bar:
        If True, a progress bar will be displayed.
    kwargs:
        Keyword arguments to be passed to the function.z
    """
    with MessageBuffer(flush_at_end) as msg_buf:
        tasks = [
            dask.delayed(redirect_print_explicitly(func, msg_buf))(item, **kwargs)
            for item in iterable
        ]
        print(f"Performing parallel execution of {func.__name__} ({len(tasks)} tasks).")
        if progress_bar:
            with ProgressBar():
                results = dask.compute(*tasks)
        else:
            results = dask.compute(*tasks)
    return results


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


def async_parallelize(func: Callable, iterable: Iterable, **kwargs):
    """Work in progress"""

    async def inner(func_, iterable_, **kwargs_):
        async with AsyncMessageBuffer() as msg_buf:
            tasks = [
                dask.delayed(redirect_print_explicitly(func_, msg_buf))(item, **kwargs_)
                for item in iterable_
            ]
            print(
                f"Performing parallel execution of {func.__name__} "
                f"({len(tasks)} tasks)."
            )
            with ProgressBar():
                results = dask.compute(*tasks)
        return results

    return asyncio.run(inner(func, iterable, **kwargs))


class RedirectStdout(object):
    """Can be used as a decorator or context manager to temporarily redirect
    stdout to a buffer.

    Source
    ------
    Adapted in accordance to: https://gist.github.com/jasonbartz/8480004
    """

    def __init__(self, buffer: MessageBuffer, **kwargs):
        """Init and set vars"""
        self.buffer: MessageBuffer = buffer
        self.write_func = self.buffer.write
        self.kwargs = kwargs

    def __call__(self, function):
        """Call the function"""

        def wrapped_function(*args, **kwargs):
            with StringIO() as buf, redirect_stdout(buf):
                return_val = function(*args, **kwargs)
                out = buf.getvalue()
            with suppress(AttributeError):
                # sys.stdout.close()
                sys.stdout = sys.__stdout__
                if sys.stdout.closed:
                    raise ValueError("sys.stdout is closed.")
            self.write_func(out)
            return return_val

        return wrapped_function


# todo: fix
#  - If no message buffer is provided to file_like, the messages are not stored


# testing redirect
if __name__ == "__main__":
    from datetime import datetime
    from time import sleep

    print("Redirecting print messages to a buffer.")
    message_buffer = MessageBuffer()
    io_buffer = StringIO()
    file_as_buffer = open("xx.txt", "w")

    def prepend_timestamp(line):
        return f"{datetime.now().isoformat()}: {line}"

    def create_list_item(i, debug: bool = True):
        if debug:
            print(f"Creating item {i + 1}.")
        sleep(0.1)
        return i**2

    def create_list_dask(length: int, debug: bool = True) -> list[int]:
        message_buffer_ = MessageBuffer()
        # todo: line_print="line_numbers" doesn't return any message

        @redirect_print(
            file_like=message_buffer_,  # line_print=prepend_timestamp
        )
        def in_parallel(i_, length_, debug_: bool = True):
            if debug_:
                print(f"Creating item {i_ + 1} of {length_}")
            sleep(0.1)
            return i_**2

        tasks = []
        for i in range(length):
            tasks.append(dask.delayed(in_parallel)(i, length, debug))
        with ProgressBar():
            result = dask.compute(*tasks)
        sleep(0.1)
        if debug:
            print("Messages collected during parallel execution:")
            message_buffer_.flush()

        return result

    def create_list_dask_1(length: int, debug: bool = True) -> list[int]:
        @redirect_print
        def in_parallel(i_, length_, debug_: bool = True):
            if debug_:
                print(f"Creating item {i_ + 1} of {length_}")
            sleep(0.1)
            return i_**2

        tasks = []
        for i in range(length):
            tasks.append(dask.delayed(in_parallel)(i, length, debug))
        with ProgressBar():
            result = dask.compute(*tasks)

        return result

    def create_list_dask_2(length: int, debug: bool = True) -> list[int]:
        message_buffer_ = MessageBuffer()

        @RedirectStdout(buffer=message_buffer_)
        def in_parallel(i_, length_, debug_: bool = True):
            if debug_:
                print(f"Creating item {i_ + 1} of {length_}")
            sleep(0.1)
            return i_**2

        tasks = []
        for i in range(length):
            tasks.append(dask.delayed(in_parallel)(i, length, debug))
        with ProgressBar():
            result = dask.compute(*tasks)

        message_buffer_.flush()

        return result

    @redirect_print(file_like=message_buffer)
    def create_list(length: int) -> list[int]:
        print(f"Creating a list of length {length}")
        for i in range(length):
            sleep(0.1)
            print(f"Creating item {i + 1} of {length}")
        return [i for i in range(length)]

    @redirect_print
    def create_list_1(length: int) -> list[int]:
        print(f"Creating a list of length {length}")
        for i in range(length):
            sleep(0.1)
            print(f"Creating item {i + 1} of {length}")
        return [i for i in range(length)]

    @redirect_print_explicitly()
    def create_list_2(length: int) -> list[int]:
        print(f"Creating a list of length {length}")
        for i in range(length):
            sleep(0.1)
            print(f"Creating item {i + 1} of {length}")
        return [i for i in range(length)]

    @redirect_print(file_like=Path("xx.txt"))
    def create_list_3(length: int) -> list[int]:
        print(f"Creating a list of length {length}")
        for i in range(length):
            sleep(0.1)
            print(f"Creating item {i + 1} of {length}")
        return [i for i in range(length)]

    # @redirect_print(file_like=file_as_buffer)
    # def print_lines(num_lines):
    #     for i in range(num_lines):
    #         print(f'Line #{i + 1}')

    @redirect_print(file_like=message_buffer)
    def print_lines_1(num_lines):
        for i in range(num_lines):
            print(f"Line #{i + 1}")

    @redirect_print_explicitly(file_like=message_buffer, line_print=prepend_timestamp)
    def print_lines_2(num_lines):
        for i in range(num_lines):
            print(f"Line #{i + 1}")

    @redirect_print
    def print_lines_3(num_lines):
        for i in range(num_lines):
            print(f"Line #{i + 1}")

    print("Pre-execution")
    # print_lines(10)
    # print_lines_1(10)
    # print_lines_2(10)
    # print_lines_3(10)
    # test_list_dask = create_list_dask(10)
    # test_list_dask_1 = create_list_dask_1(10)
    # test_list_dask_2 = create_list_dask_2(10)
    test_list_new = parallelize(
        create_list_item,
        range(1000),
        flush_at_end=True,
    )
    # test_list_new = async_parallelize(create_list_item, range(10), debug=True)
    # test_list = create_list(10)
    # test_list_1 = create_list_1(10)
    # test_list_2 = create_list_2(10)
    # test_list_3 = create_list_3(10)
    print("Post-execution")
    print("Messages from the buffer:")
    message_buffer.flush()
    file_as_buffer.close()
    print("Messages from the file buffer:")
    with open("xx.txt", "r") as f:
        for line_ in f.readlines():
            print(line_, end="")
