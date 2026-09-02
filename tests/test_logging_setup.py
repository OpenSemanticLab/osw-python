"""Offline tests for the osw logging setup and its capture in parallelize.

Covers #130: prints replaced by logging, on by default, and routed per worker
thread so a parallel batch does not garble its own progress bar.
"""

import logging

import pytest

import osw
from osw.utils.util import ThreadRoutedLogHandler, handler_chain, parallelize


class ListHandler(logging.Handler):
    """Collects records so a test can assert on them"""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record: logging.LogRecord):
        self.records.append(record)

    def messages(self, name: str = None):
        return [r.getMessage() for r in self.records if name is None or r.name == name]


@pytest.fixture
def osw_logger():
    """Hands out the osw logger and puts its global state back afterwards"""
    logger = logging.getLogger("osw")
    saved = (logger.handlers[:], logger.level, logger.propagate)
    yield logger
    logger.handlers, logger.level, logger.propagate = saved


@pytest.fixture
def collected(osw_logger):
    """The osw logger with a single collecting handler on it"""
    handler = ListHandler()
    osw_logger.handlers = [handler]
    osw_logger.propagate = False
    osw_logger.setLevel(logging.DEBUG)
    return handler


def test_the_package_attaches_its_own_handler_on_import():
    """Logging is on by default, so a caller who configures nothing still sees
    what osw is doing."""
    names = [h.get_name() for h in logging.getLogger("osw").handlers]

    assert "osw-default" in names


@pytest.mark.parametrize(
    "value, expected",
    [
        ("DEBUG", logging.DEBUG),
        ("debug", logging.DEBUG),
        ("  warning  ", logging.WARNING),
        ("10", 10),
        ("OFF", osw.OFF),
        ("NONE", osw.OFF),
        ("SILENT", osw.OFF),
        ("nonsense", osw.DEFAULT_LOG_LEVEL),
        ("", osw.DEFAULT_LOG_LEVEL),
    ],
)
def test_the_environment_variable_is_parsed_leniently(value, expected):
    """An unusable value falls back rather than raising at import time."""
    assert osw._parse_level(value) == expected


def test_enable_logging_reads_the_environment_variable(osw_logger, monkeypatch):
    monkeypatch.setenv(osw.LOG_LEVEL_ENV_VAR, "WARNING")

    osw.enable_logging()

    assert osw_logger.level == logging.WARNING


def test_enable_logging_does_not_stack_handlers(osw_logger):
    """Calling it again replaces the handler instead of adding a second one,
    so messages are not emitted twice."""
    osw.enable_logging()
    osw.enable_logging()

    assert len(osw_default_handlers(osw_logger)) == 1


def osw_default_handlers(logger):
    """The handlers osw attached itself

    Membership rather than list equality, because pytest's logging plugin
    attaches its own capture handlers to any logger that does not propagate,
    which the osw logger does not while the default handler is on it.
    """
    return [h for h in logger.handlers if h.get_name() == "osw-default"]


def test_disable_logging_leaves_a_foreign_handler_alone(osw_logger):
    """Only the handler osw attached itself is removed. A handler the calling
    application added keeps receiving records."""
    foreign = ListHandler()
    osw.enable_logging()
    osw_logger.addHandler(foreign)

    osw.disable_logging()

    assert foreign in osw_logger.handlers
    assert osw_default_handlers(osw_logger) == []


def test_disable_logging_restores_propagation(osw_logger):
    """Handing control back to the root logger is what lets an application take
    over with basicConfig()."""
    osw.enable_logging()
    assert osw_logger.propagate is False

    osw.disable_logging()

    assert osw_logger.propagate is True


def test_set_log_level_filters_what_is_emitted(collected, osw_logger):
    osw.set_log_level(logging.WARNING)
    log = logging.getLogger("osw.somewhere")

    log.info("routine progress")
    log.warning("something worth saying")

    assert collected.messages() == ["something worth saying"]


def test_handler_chain_stops_where_propagation_stops(osw_logger):
    own = ListHandler()
    osw_logger.handlers = [own]
    osw_logger.propagate = False

    assert handler_chain(osw_logger) == [own]


def test_handler_chain_includes_ancestors_while_propagating(osw_logger):
    """After disable_logging() the records land on the root logger, so the
    chain has to keep walking to find where they actually go."""
    own = ListHandler()
    inherited = ListHandler()
    osw_logger.handlers = [own]
    osw_logger.propagate = True
    root = logging.getLogger()
    root.addHandler(inherited)
    try:
        chain = handler_chain(osw_logger)
    finally:
        root.removeHandler(inherited)

    assert own in chain
    assert inherited in chain


def test_an_unregistered_thread_is_forwarded(osw_logger):
    """The calling thread and tqdm keep writing straight through."""
    wrapped = ListHandler()
    handler = ThreadRoutedLogHandler([wrapped])
    osw_logger.handlers = [handler]
    osw_logger.setLevel(logging.DEBUG)

    logging.getLogger("osw.caller").info("straight through")

    assert wrapped.messages() == ["straight through"]


def test_a_registered_thread_is_buffered(osw_logger):
    wrapped = ListHandler()
    handler = ThreadRoutedLogHandler([wrapped])
    osw_logger.handlers = [handler]
    osw_logger.setLevel(logging.DEBUG)
    buffer = handler.register()
    try:
        logging.getLogger("osw.worker").info("held back")
    finally:
        handler.unregister()

    assert wrapped.messages() == []
    assert [r.getMessage() for r in buffer] == ["held back"]


WORKER = "osw.worker"


def _log_item(item):
    logging.getLogger(WORKER).info(f"handled {item}")
    return item


def test_worker_records_are_replayed_in_input_order(collected):
    """The tasks finish in whatever order they finish, so the replay is what
    puts the messages back in the order of the iterable."""
    parallelize(_log_item, [1, 2, 3, 4], flush_at_end=True, progress_bar=False)

    assert collected.messages(WORKER) == [
        "handled 1",
        "handled 2",
        "handled 3",
        "handled 4",
    ]


def test_worker_records_are_dropped_without_flush_at_end(collected):
    """flush_at_end=False means quiet, which is what debug=False asks for."""
    parallelize(_log_item, [1, 2, 3], flush_at_end=False, progress_bar=False)

    assert collected.messages(WORKER) == []


def test_the_logger_is_restored_afterwards(collected, osw_logger):
    parallelize(_log_item, [1], flush_at_end=True, progress_bar=False)

    assert collected in osw_logger.handlers
    assert not [h for h in osw_logger.handlers if isinstance(h, ThreadRoutedLogHandler)]
    assert osw_logger.propagate is False


def _fail_on_item(item):
    logging.getLogger(WORKER).info(f"about to fail on {item}")
    raise ValueError(item)


def test_a_failed_batch_still_replays_and_restores(collected, osw_logger):
    """The replay sits in a finally block, so a batch that raised still reports
    what its tasks had to say."""
    with pytest.raises(ValueError):
        parallelize(_fail_on_item, [7], flush_at_end=True, progress_bar=False)

    assert collected.messages(WORKER) == ["about to fail on 7"]
    assert collected in osw_logger.handlers
    assert not [h for h in osw_logger.handlers if isinstance(h, ThreadRoutedLogHandler)]
