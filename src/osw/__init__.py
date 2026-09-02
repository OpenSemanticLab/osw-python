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
_level_is_ours = False
"""Whether the level on the osw logger is the one osw picked for itself. A
level the calling code asked for is left alone when osw hands over."""


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


def _application_handles_records() -> bool:
    """Whether the calling code already has somewhere for osw's records to go

    Walks what logging.Logger.callHandlers walks above the osw logger. Any
    handler found up there belongs to the calling application, so osw writing
    its own copy would only duplicate what that handler already reports.
    """
    if not _logger.propagate:
        # something is deliberately holding the records at the osw logger,
        # parallelize while it captures a batch among them
        return False
    current = _logger.parent
    while current:
        if current.handlers:
            return True
        if not current.propagate:
            return False
        current = current.parent
    return False


class _DefaultHandler(logging.StreamHandler):
    """The handler osw attaches while nothing else is listening

    Steps aside the first time it finds that the calling application has
    configured logging of its own. The check belongs here rather than at import
    time because a script normally imports osw before it calls basicConfig().
    """

    def emit(self, record: logging.LogRecord):
        if _application_handles_records():
            _hand_over()
            return
        super().emit(record)


def _detach():
    """Removes the handler osw attached, leaving any other one in place

    Rebinds the list instead of calling removeHandler, because this also runs
    from inside the handler's own emit, where callHandlers is iterating that
    very list.
    """
    detached = [h for h in _logger.handlers if h.get_name() == _DEFAULT_HANDLER_NAME]
    _logger.handlers = [h for h in _logger.handlers if h not in detached]
    for handler in detached:
        handler.close()


def _hand_over():
    """Gives the application's own logging setup sole charge of osw's records

    Drops osw's handler so nothing is written twice, and drops the level osw
    picked so the application's level applies. A level the calling code asked
    for, through set_log_level, enable_logging or the environment variable, is
    kept, since that is how one asks for osw's DEBUG records in an aggregated
    setup.
    """
    global _level_is_ours
    _detach()
    if _level_is_ours:
        _logger.setLevel(logging.NOTSET)
        _level_is_ours = False


def enable_logging(level=None, stream=None) -> logging.Handler:
    """Attaches osw's own handler to the osw logger

    Called on import when nothing else handles the records, so osw reports what
    it is doing without the calling code configuring anything. Call it again to
    take the output back after disable_logging(), or to send it elsewhere.

    The handler detaches itself as soon as the calling application configures
    logging, so records are never written twice.

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
    global _level_is_ours
    asked_for = level is not None or LOG_LEVEL_ENV_VAR in os.environ
    if level is None:
        level = _parse_level(os.environ.get(LOG_LEVEL_ENV_VAR, ""))
    _detach()
    handler = _DefaultHandler(sys.stdout if stream is None else stream)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.set_name(_DEFAULT_HANDLER_NAME)
    _logger.addHandler(handler)
    _logger.setLevel(level)
    _level_is_ours = not asked_for
    return handler


def disable_logging():
    """Hands the osw logger over to the calling application

    Removes the handler osw attached and the level it picked, so the records
    follow whatever the application configured, on the 'osw' logger or on the
    root logger above it. A handler the calling code added to the 'osw' logger
    is left in place.

    Not needed in order to aggregate osw's records. They propagate to the root
    logger at all times, and osw's own handler steps aside by itself once
    anything else is listening. Call this to be explicit about it, or when a
    handler was added to the 'osw' logger directly, which osw cannot tell apart
    from one of its own callers.
    """
    global _level_is_ours
    _detach()
    _logger.setLevel(logging.NOTSET)
    _level_is_ours = False


def set_log_level(level):
    """Sets how much osw reports

    The level survives a hand-over to the application's own logging setup, so
    this is also how to ask for osw's DEBUG records in an aggregated setup.

    Parameters
    ----------
    level
        a level name or number, e.g. 'DEBUG', 'WARNING', or logging.WARNING.
        Pass osw.OFF to silence osw everywhere, its own handler and the
        application's alike.
    """
    global _level_is_ours
    _logger.setLevel(level)
    _level_is_ours = False


def _configure_on_import():
    """Sets logging up the way an interpreter that configured none needs it"""
    if _application_handles_records():
        # logging was configured before osw was imported, so the records
        # already have somewhere to go and only the level is osw's to set
        if LOG_LEVEL_ENV_VAR in os.environ:
            set_log_level(_parse_level(os.environ[LOG_LEVEL_ENV_VAR]))
        return
    enable_logging()
    if LOG_LEVEL_ENV_VAR not in os.environ:
        # once per interpreter, since this module is imported once. Sent
        # through the logger itself, so it disappears with everything else as
        # soon as the level is raised or the environment variable is set.
        _logger.info(
            "osw logs at %s on the 'osw' logger. Use osw.set_log_level"
            "('WARNING') to see less, osw.disable_logging() to switch it off, "
            "or set %s=OFF before import. Configuring logging yourself, e.g. "
            "with logging.basicConfig(), takes the output over automatically.",
            logging.getLevelName(_logger.level),
            LOG_LEVEL_ENV_VAR,
        )


_configure_on_import()
