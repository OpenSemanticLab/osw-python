"""Unit tests for upload error reporting in osw.controller.file.wiki.

Regression guard for #51: a file rejected because of its extension must produce
an error that names the extension, instead of a bare MediaWiki API code.
"""

import mwclient.errors
import pytest

from osw.controller.file.wiki import (
    get_allowed_file_extensions,
    reraise_upload_error,
)


class _FakeSite:
    host = "wiki.example.org"

    def __init__(self, extensions=None, fail=False):
        self._extensions = extensions
        self._fail = fail

    def api(self, *args, **kwargs):
        if self._fail:
            raise RuntimeError("siteinfo unavailable")
        return {"query": {"fileextensions": [{"ext": e} for e in self._extensions]}}


def _api_error(code):
    return mwclient.errors.APIError(code, "info", {})


@pytest.mark.parametrize(
    "code", ["filetype-banned", "filetype-banned-type", "filetype-badtype"]
)
def test_rejected_extension_names_the_extension(code):
    site = _FakeSite(extensions=["png", "pdf"])

    with pytest.raises(ValueError) as exc_info:
        reraise_upload_error(_api_error(code), site, "OSW123.exe", ".exe")

    message = str(exc_info.value)
    assert ".exe" in message
    assert "OSW123.exe" in message
    assert "wiki.example.org" in message
    assert "pdf, png" in message  # allowed extensions, sorted


def test_original_error_is_chained():
    site = _FakeSite(extensions=["png"])
    original = _api_error("filetype-banned")

    with pytest.raises(ValueError) as exc_info:
        reraise_upload_error(original, site, "OSW123.exe", ".exe")

    assert exc_info.value.__cause__ is original


def test_unrelated_api_error_is_reraised_unchanged():
    site = _FakeSite(extensions=["png"])
    original = _api_error("readapidenied")

    with pytest.raises(mwclient.errors.APIError) as exc_info:
        reraise_upload_error(original, site, "OSW123.png", ".png")

    assert exc_info.value is original


def test_message_omits_the_hint_when_siteinfo_fails():
    """A failing siteinfo lookup must not mask the upload error."""
    site = _FakeSite(fail=True)

    with pytest.raises(ValueError) as exc_info:
        reraise_upload_error(_api_error("filetype-banned"), site, "a.exe", ".exe")

    assert "allowed on this wiki" not in str(exc_info.value)
    assert ".exe" in str(exc_info.value)


def test_get_allowed_file_extensions_returns_none_on_failure():
    assert get_allowed_file_extensions(_FakeSite(fail=True)) is None


def test_get_allowed_file_extensions_reads_siteinfo():
    site = _FakeSite(extensions=["png", "jpg"])

    assert get_allowed_file_extensions(site) == ["png", "jpg"]
