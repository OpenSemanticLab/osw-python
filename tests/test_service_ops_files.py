"""Unit tests for osw.service.ops.files (Operation.fn called directly).

Runs in the plain dev env (no mcp extra, no network): ``WikiFileController``
is replaced with a fake factory that records its constructor arguments, so
every test can inspect the title/namespace a real controller would have
derived without touching a wiki.
"""

from unittest.mock import MagicMock

import pytest

from osw.core import OverwriteOptions
from osw.service import errors
from osw.service.config import Settings
from osw.service.context import Context, Policy
from osw.service.ledger import LedgerRecord
from osw.service.ops import files
from osw.service.registry import REGISTRY


class _WfFactory:
    """Stands in for ``WikiFileController``, recording every instance made.

    ``set_stream`` configures the ``.get()`` return value of instances made
    *after* the call, mirroring how a real controller's stream only exists
    once ``get()`` is invoked on it.
    """

    def __init__(self):
        self.created: list = []
        self._stream = None

    def set_stream(self, stream) -> None:
        self._stream = stream

    def __call__(self, **kwargs):
        wf = MagicMock()
        wf.namespace = kwargs.get("namespace") or "File"
        wf.title = kwargs.get("title")
        wf.url = f"https://wiki.example.org/wiki/{wf.namespace}:{wf.title}"
        if self._stream is not None:
            wf.get.return_value = self._stream
        self.created.append(wf)
        return wf


@pytest.fixture
def wf_factory(monkeypatch) -> _WfFactory:
    """Replace ``files.WikiFileController`` with a fake, recording instances."""
    factory = _WfFactory()
    monkeypatch.setattr(files, "WikiFileController", MagicMock(side_effect=factory))
    return factory


def _ctx() -> Context:
    settings = Settings(domain="wiki.example.org", username="u", password="p")
    return Context(settings, Policy(), osw=MagicMock(), ledger=MagicMock())


def _set_page_exists(ctx: Context, exists: bool):
    page = MagicMock()
    page.exists = exists
    ctx.osw.site.get_page.return_value.pages = [page]
    return page


# -- get_file_info --------------------------------------------------------------
def test_get_file_info_success(wf_factory):
    ctx = _ctx()
    _set_page_exists(ctx, True)
    stream = MagicMock()
    stream.headers = {"Content-Length": "1234", "Content-Type": "image/png"}
    wf_factory.set_stream(stream)

    result = files.get_file_info(ctx, "File:OSWabc123.png")

    wf = wf_factory.created[-1]
    assert wf.title == "OSWabc123.png"
    assert result == {
        "title": "File:OSWabc123.png",
        "exists": True,
        "url": wf.url,
        "size": 1234,
        "media_type": "image/png",
    }
    stream.close.assert_called_once()


def test_get_file_info_missing(wf_factory):
    ctx = _ctx()
    _set_page_exists(ctx, False)

    result = files.get_file_info(ctx, "File:doesnotexist.png")

    assert result == {
        "title": "File:doesnotexist.png",
        "exists": False,
        "url": None,
        "size": None,
        "media_type": None,
    }
    assert wf_factory.created == []  # no controller built for a missing file


# -- read_file_text ---------------------------------------------------------------
def test_read_file_text_success(wf_factory):
    ctx = _ctx()
    _set_page_exists(ctx, True)
    stream = MagicMock()
    stream.read.return_value = b"hello world"
    wf_factory.set_stream(stream)

    result = files.read_file_text(ctx, "File:OSWabc.txt")

    assert result == {
        "title": "File:OSWabc.txt",
        "content": "hello world",
        "encoding": "utf-8",
        "truncated": False,
    }
    stream.read.assert_called_once_with(ctx.settings.max_chars + 1)
    stream.close.assert_called_once()


def test_read_file_text_truncates(wf_factory):
    ctx = _ctx()
    _set_page_exists(ctx, True)
    stream = MagicMock()
    stream.read.return_value = b"x" * 6  # cap + 1 bytes, cap == limit == 5
    wf_factory.set_stream(stream)

    result = files.read_file_text(ctx, "File:OSWabc.txt", limit=5)

    assert result["truncated"] is True
    assert result["content"] == "x" * 5
    stream.read.assert_called_once_with(6)


def test_read_file_text_truncation_may_split_a_multibyte_character(wf_factory):
    """A valid text file cut mid-character must not be reported as binary.

    ``limit`` counts bytes, so truncating can land inside a multi-byte
    character. The incomplete trailing sequence is dropped; raising
    BinaryContent here would tell the user to download a file that reads
    perfectly well.
    """
    ctx = _ctx()
    _set_page_exists(ctx, True)
    stream = MagicMock()
    # 'ä' is two bytes starting at offset 9, so a cap of 10 splits it.
    stream.read.return_value = ("a" * 9 + "ä" + "b" * 50).encode("utf-8")[:11]
    wf_factory.set_stream(stream)

    result = files.read_file_text(ctx, "File:OSWabc.txt", limit=10)

    assert result["truncated"] is True
    assert result["content"] == "a" * 9


def test_read_file_text_missing_raises_not_found(wf_factory):
    ctx = _ctx()
    _set_page_exists(ctx, False)

    with pytest.raises(errors.NotFound):
        files.read_file_text(ctx, "File:doesnotexist.txt")
    assert wf_factory.created == []


def test_read_file_text_binary_raises_binary_content(wf_factory):
    ctx = _ctx()
    _set_page_exists(ctx, True)
    stream = MagicMock()
    stream.read.return_value = b"\xff\xfe\x00\x01"
    wf_factory.set_stream(stream)

    with pytest.raises(errors.BinaryContent):
        files.read_file_text(ctx, "File:OSWabc.bin")


# -- write_file_text ----------------------------------------------------------
def test_write_file_text_success(wf_factory):
    ctx = _ctx()

    result = files.write_file_text(ctx, "File:OSWabc.txt", "hello")

    wf = wf_factory.created[-1]
    assert wf.title == "OSWabc.txt"
    wf.put.assert_called_once()
    (stream_arg,), put_kwargs = wf.put.call_args
    assert stream_arg.read() == b"hello"
    assert stream_arg.name == "OSWabc.txt"
    assert put_kwargs == {"overwrite": OverwriteOptions.true}

    assert result == {"title": "File:OSWabc.txt", "url": wf.url}


def test_write_file_text_custom_name_and_no_overwrite(wf_factory):
    ctx = _ctx()

    files.write_file_text(
        ctx, "File:OSWabc.txt", "hello", name="renamed.txt", overwrite=False
    )

    wf = wf_factory.created[-1]
    (stream_arg,), put_kwargs = wf.put.call_args
    assert stream_arg.name == "renamed.txt"
    assert put_kwargs == {"overwrite": OverwriteOptions.false}


def test_write_file_text_records_ledger_entry():
    op = REGISTRY["write_file_text"]
    result = {"title": "File:OSWabc.txt", "url": "https://example.org/x"}

    records = op.records(result)

    assert records == [
        LedgerRecord(title="File:OSWabc.txt", op="create", slots=["jsondata"])
    ]
