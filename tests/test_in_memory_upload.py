"""Unit tests for uploading a file from an in-memory stream (issue #140).

Fully offline: no network, no live wiki. The upload path is cut short by
replacing ``WikiFileController.from_other`` with a stub that records the
source controller it was handed, so the dispatch in ``UploadFileResult`` can
be checked without touching a wiki.
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock

import pytest

import osw.express
from osw.controller.file.memory import InMemoryController


def test_controller_accepts_a_caller_supplied_stream():
    stream = BytesIO(b"payload")
    controller = InMemoryController(stream=stream)
    assert controller.get() is stream
    assert controller.get().read() == b"payload"


def test_controller_defaults_to_an_empty_binary_buffer():
    controller = InMemoryController()
    assert isinstance(controller.stream, BytesIO)
    assert controller.stream.getvalue() == b""


def test_controller_put_copies_into_the_stream():
    controller = InMemoryController()
    controller.put(BytesIO(b"payload"))
    assert controller.stream.getvalue() == b"payload"


def test_upload_wraps_a_stream_in_an_in_memory_controller(monkeypatch):
    """A BytesIO must reach WikiFileController as an InMemoryController.

    Guards the duck-typed source check in UploadFileResult.__init__: an
    ``isinstance(source, IO)`` test never matches, because typing.IO is not
    runtime-checkable.
    """
    stream = BytesIO(b"payload")
    seen = {}

    class _StopBeforeUpload(Exception):
        pass

    def _fake_from_other(other, osw, **data):
        seen["source_file_controller"] = other
        raise _StopBeforeUpload

    monkeypatch.setattr(
        osw.express.WikiFileController,
        "from_other",
        staticmethod(_fake_from_other),
    )

    with pytest.raises(_StopBeforeUpload):
        osw.express.UploadFileResult(
            source=stream,
            osw_express=MagicMock(),
            target_fpt="File:Test.bin",
        )

    controller = seen["source_file_controller"]
    assert isinstance(controller, InMemoryController)
    assert controller.get() is stream


def test_upload_rejects_a_source_that_is_not_file_like():
    with pytest.raises(ValueError, match="must be a LocalFileController"):
        osw.express.UploadFileResult(source=object(), osw_express=MagicMock())
