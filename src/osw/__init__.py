import logging
import os
import sys
from importlib.metadata import PackageNotFoundError, version  # pragma: no cover

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = __name__
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError

LOG_LEVEL_ENV_VAR = "OSW_LOG_LEVEL"
"""Name of the environment variable read for the initial log level. Accepts a
level name, a level number, or 'OFF' to start silent."""
DEFAULT_LOG_LEVEL = logging.INFO
"""Level the osw logger starts at when the environment variable is unset"""
LOG_FORMAT = "[%(levelname)s] %(name)s: %(message)s"
OFF = logging.CRITICAL + 1
"""Level above every real record, so setting it silences the logger"""

_DEFAULT_HANDLER_NAME = "osw-default"
_logger = logging.getLogger(__name__)


def _parse_level(value: str) -> int:
    """Turns the environment variable into a level, tolerating junk

    Parameters
    ----------
    value
        a level name such as 'DEBUG', a level number such as '10', or 'OFF'

    Returns
    -------
        the level, or DEFAULT_LOG_LEVEL if the value names none
    """
    cleaned = value.strip().upper()
    if cleaned in ("OFF", "NONE", "SILENT"):
        return OFF
    if cleaned.isdigit():
        return int(cleaned)
    # getLevelName maps an unknown name to the string 'Level %s', not to a number
    level = logging.getLevelName(cleaned)
    if isinstance(level, int):
        return level
    return DEFAULT_LOG_LEVEL


def enable_logging(level=None, stream=None) -> logging.Handler:
    """Attaches the default handler to the osw logger

    Called once on import, so osw reports what it is doing without the calling
    code configuring anything. Call it again to restore the handler after
    disable_logging(), or to send the records to another stream.

    Parameters
    ----------
    level
        a level name or number. Defaults to the environment variable, then to
        DEFAULT_LOG_LEVEL.
    stream
        where to write. Defaults to sys.stdout, which is where the print calls
        this replaced used to go.

    Returns
    -------
        the attached handler
    """
    if level is None:
        level = _parse_level(os.environ.get(LOG_LEVEL_ENV_VAR, ""))
    disable_logging()
    handler = logging.StreamHandler(sys.stdout if stream is None else stream)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.set_name(_DEFAULT_HANDLER_NAME)
    _logger.addHandler(handler)
    _logger.setLevel(level)
    # the records are handled here, so passing them to the root logger as well
    # would print everything twice for anyone who called basicConfig()
    _logger.propagate = False
    return handler


def disable_logging():
    """Removes the default handler, leaving osw silent

    Only the handler osw attached itself is removed, so a handler the calling
    code added to the 'osw' logger keeps receiving records. Records propagate
    to the root logger again, which is what a library is normally expected to
    do, and lets the calling code take over with basicConfig().
    """
    for handler in list(_logger.handlers):
        if handler.get_name() == _DEFAULT_HANDLER_NAME:
            _logger.removeHandler(handler)
            handler.close()
    _logger.propagate = True


def set_log_level(level):
    """Sets how much osw reports

    Parameters
    ----------
    level
        a level name or number, e.g. 'DEBUG', 'WARNING', or logging.WARNING.
        Pass osw.OFF to silence osw without detaching the handler.
    """
    _logger.setLevel(level)


enable_logging()

if os.environ.get(LOG_LEVEL_ENV_VAR) is None:
    # once per interpreter, since this module is only imported once. Sent
    # through the logger itself, so it disappears with everything else as soon
    # as the level is raised or the environment variable is set.
    _logger.info(
        "osw logs at %s. Use osw.set_log_level('WARNING') to see less, "
        "osw.disable_logging() to switch it off, or set %s=OFF before import.",
        logging.getLevelName(_logger.level),
        LOG_LEVEL_ENV_VAR,
    )
