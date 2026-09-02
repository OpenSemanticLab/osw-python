"""Unit tests for upload error reporting in osw.controller.file.wiki.

Regression guard for #51: a file rejected because of its extension must produce
an error that names the extension, instead of a bare MediaWiki API code.

Also guards the silent-failure path: mwclient raises only on an 'error' key, so
an upload MediaWiki declined by other means must be caught by inspecting the
returned result.
"""

import mwclient.errors
import pytest

from osw.controller.file.wiki import (
    assert_upload_success,
    format_allowed_extensions,
    reraise_upload_error,
    store_params_for_upload,
)
from osw.wtsite import WtSite


class _FakeMwSite:
    """Stands in for the mwclient.Site behind WtSite.mw_site."""

    host = "wiki.example.org"

    def __init__(self, extensions=None, fail=False):
        self._extensions = extensions or []
        self._fail = fail
        self.api_calls = 0

    def api(self, *args, **kwargs):
        self.api_calls += 1
        if self._fail:
            raise RuntimeError("siteinfo unavailable")
        return {"query": {"fileextensions": [{"ext": e} for e in self._extensions]}}


def _fake_site(extensions=None, fail=False):
    """Builds a minimal WtSite carrying a fake mwclient site, bypassing __init__."""
    ws = WtSite.__new__(WtSite)
    ws._site = _FakeMwSite(extensions=extensions, fail=fail)
    ws._allowed_file_extensions = None
    return ws


def _api_error(code):
    return mwclient.errors.APIError(code, "info", {})


@pytest.mark.parametrize(
    "code", ["filetype-banned", "filetype-banned-type", "filetype-badtype"]
)
def test_rejected_extension_names_the_extension(code):
    site = _fake_site(extensions=["png", "pdf"])

    with pytest.raises(ValueError) as exc_info:
        reraise_upload_error(_api_error(code), site, "OSW123.exe", ".exe")

    message = str(exc_info.value)
    assert ".exe" in message
    assert "OSW123.exe" in message
    assert "wiki.example.org" in message
    assert "pdf, png" in message  # allowed extensions, sorted


def test_original_error_is_chained():
    site = _fake_site(extensions=["png"])
    original = _api_error("filetype-banned")

    with pytest.raises(ValueError) as exc_info:
        reraise_upload_error(original, site, "OSW123.exe", ".exe")

    assert exc_info.value.__cause__ is original


def test_unrelated_api_error_is_reraised_unchanged():
    site = _fake_site(extensions=["png"])
    original = _api_error("readapidenied")

    with pytest.raises(mwclient.errors.APIError) as exc_info:
        reraise_upload_error(original, site, "OSW123.png", ".png")

    assert exc_info.value is original


def test_message_omits_the_hint_when_siteinfo_fails():
    """A failing siteinfo lookup must not mask the upload error."""
    site = _fake_site(fail=True)

    with pytest.raises(ValueError) as exc_info:
        reraise_upload_error(_api_error("filetype-banned"), site, "a.exe", ".exe")

    message = str(exc_info.value)
    assert "Extensions allowed" not in message
    assert "clear_allowed_file_extensions_cache" not in message
    assert ".exe" in message


def test_message_names_the_fetch_time_and_the_reset_hint():
    site = _fake_site(extensions=["png", "pdf"])

    with pytest.raises(ValueError) as exc_info:
        reraise_upload_error(_api_error("filetype-banned"), site, "a.exe", ".exe")

    message = str(exc_info.value)
    fetched_at = site.get_allowed_file_extensions().fetched_at
    assert f"{fetched_at:%Y-%m-%d %H:%M:%S}" in message
    assert "osw.site.clear_allowed_file_extensions_cache()" in message


def test_a_second_rejected_upload_does_not_query_the_wiki_again():
    site = _fake_site(extensions=["png", "pdf"])

    with pytest.raises(ValueError):
        reraise_upload_error(_api_error("filetype-banned"), site, "a.exe", ".exe")
    with pytest.raises(ValueError):
        reraise_upload_error(_api_error("filetype-banned"), site, "b.exe", ".exe")

    assert site.mw_site.api_calls == 1


def test_format_allowed_extensions_is_empty_when_extensions_is_none():
    allowed = WtSite.AllowedFileExtensionsResult(extensions=None, fetched_at=None)

    assert format_allowed_extensions(allowed) == ""


def test_format_allowed_extensions_is_empty_when_extensions_is_empty():
    allowed = WtSite.AllowedFileExtensionsResult(extensions=[], fetched_at=None)

    assert format_allowed_extensions(allowed) == ""


def test_successful_upload_passes():
    assert (
        assert_upload_success({"result": "Success"}, "a.png", "wiki.example.org")
        is None
    )


@pytest.mark.parametrize("result", [{}, None, {"result": "Poll"}])
def test_upload_without_success_raises(result):
    """Anything but a Success result means the file did not arrive."""
    with pytest.raises(ValueError) as exc_info:
        assert_upload_success(result, "a.png", "wiki.example.org")

    assert "a.png" in str(exc_info.value)
    assert "wiki.example.org" in str(exc_info.value)


def test_a_page_the_upload_created_gets_its_metadata_written():
    """Otherwise store_entity keeps the empty page the upload just left behind."""
    assert store_params_for_upload({}, page_existed=False) == {
        "overwrite": "replace remote"
    }


def test_an_existing_page_keeps_the_callers_overwrite_policy():
    se_params = {"overwrite": "keep existing", "edit_comment": "hi"}

    assert store_params_for_upload(se_params, page_existed=True) == se_params


def test_store_params_are_not_mutated():
    se_params = {"edit_comment": "hi"}

    store_params_for_upload(se_params, page_existed=False)

    assert se_params == {"edit_comment": "hi"}


def test_warned_upload_reports_the_warnings():
    result = {"result": "Warning", "warnings": {"badfilename": "a_png"}}

    with pytest.raises(ValueError) as exc_info:
        assert_upload_success(result, "a.png", "wiki.example.org")

    assert "badfilename" in str(exc_info.value)
