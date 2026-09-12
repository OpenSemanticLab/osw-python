"""Offline tests for the uri property of the file controllers.

Covers #68: every controller reports where its file lives, in the URI scheme of
its own storage backend.
"""

from pathlib import Path
from types import SimpleNamespace
from typing import IO, Any, Dict

from osw.controller.file.base import FileController
from osw.controller.file.local import LocalFileController
from osw.controller.file.memory import InMemoryController
from osw.controller.file.remote import RemoteFileController
from osw.controller.file.wiki import WikiFileController
from osw.core import model


class OfflineRemoteFileController(RemoteFileController):
    """A remote controller carrying nothing but a url, as model.S3File does"""

    url: str

    def get(self) -> IO:
        pass

    def put(self, file: IO, **kwargs: Dict[str, Any]):
        pass


class ControllerWithoutUri(FileController):
    """A controller written before uri existed, as a third party one would be"""

    def get(self) -> IO:
        pass

    def put(self, file: IO, **kwargs: Dict[str, Any]):
        pass


def test_a_controller_that_predates_uri_still_works():
    """uri is deliberately not abstract: pydantic's ModelMetaclass extends
    ABCMeta, so an abstract property would break every controller outside this
    package that does not know about it yet."""
    controller = ControllerWithoutUri(label=[model.Label(text="Unnamed file")])

    assert controller.uri is None


def test_local_uri_is_a_file_url(tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("content", encoding="utf-8")

    uri = LocalFileController(path=path).uri

    assert uri.startswith("file:///")
    assert uri.endswith("/test.txt")


def test_local_uri_is_absolute_for_a_relative_path(tmp_path, monkeypatch):
    """as_uri() rejects a relative path, so the path has to be resolved first."""
    monkeypatch.chdir(tmp_path)

    uri = LocalFileController(path=Path("test.txt")).uri

    assert uri == (Path.cwd() / "test.txt").as_uri()


def test_local_uri_escapes_reserved_characters(tmp_path):
    uri = LocalFileController(path=tmp_path / "a file.txt").uri

    assert uri.endswith("/a%20file.txt")


def test_in_memory_uri_is_none():
    """A stream has no location, so there is nothing to point at."""
    assert InMemoryController().uri is None


def test_remote_uri_is_the_url():
    url = "s3://s3.example.org/bucket/OSW0000.txt"
    controller = OfflineRemoteFileController(
        url=url, label=[model.Label(text="OSW0000.txt")]
    )

    assert controller.uri == url


def test_wiki_uri_is_the_file_page_url():
    """WikiFileController builds url itself, so uri needs no override there."""
    page = SimpleNamespace(
        osw=SimpleNamespace(
            mw_site=SimpleNamespace(scheme="https", host="wiki.example.org")
        ),
        title="OSW0000.txt",
    )

    url = WikiFileController.url.fget(page)

    assert url == "https://wiki.example.org/wiki/File:OSW0000.txt"
    assert RemoteFileController.uri.fget(SimpleNamespace(url=url)) == url
