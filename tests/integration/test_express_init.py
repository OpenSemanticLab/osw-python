"""Tests for OswExpress initialization paths.

These tests focus on different ways to create an OswExpress instance:
- From environment variables (OSW_* and OSL_* variants)
- From arguments (domain, cred_filepath, cred_mngr)
- Error cases (no domain, invalid domain, unreachable domain)
- Context manager usage

Tests that don't require a live wiki connection use mocking.
Tests that require a live wiki connection use the wiki_domain, wiki_username,
and wiki_password fixtures (passed via CLI args).

Run with:
    tox -e test -- tests/integration/test_express_init.py
        --wiki_domain <domain> --wiki_username <user> --wiki_password <pass>

Or for unit-style tests only (no live wiki needed):
    pytest tests/integration/test_express_init.py -k "not live"
"""

import os
import warnings
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, create_autospec

import pytest
import yaml

import osw.express
from osw.auth import CredentialManager
from osw.express import (
    DataModel,
    DownloadFileResult,
    FileResult,
    UploadFileResult,
    import_with_fallback,
)
from osw.wtsite import WtSite

# -- Helpers ---------------------------------------------------------------


def create_credentials_file(
    cred_filepath: Path, wiki_domain: str, wiki_username: str, wiki_password: str
):
    cred_filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(cred_filepath, "w") as file:
        yaml.dump(
            {wiki_domain: {"username": wiki_username, "password": wiki_password}}, file
        )


@contextmanager
def clean_env_vars(*var_names):
    """Temporarily remove environment variables, restoring them on exit."""
    saved = {}
    for var in var_names:
        saved[var] = os.environ.pop(var, None)
    try:
        yield
    finally:
        for var, val in saved.items():
            if val is not None:
                os.environ[var] = val
            else:
                os.environ.pop(var, None)


ENV_VARS = [
    "OSW_WIKI_DOMAIN",
    "OSL_WIKI_DOMAIN",
    "OSW_CRED_FILEPATH",
    "OSL_CRED_FILEPATH",
]


def mock_wtsite(mocker):
    """Mock WtSite so it returns an object that passes pydantic type checks."""
    mock_site = create_autospec(WtSite, instance=True)
    mocker.patch(
        "osw.express.WtSite",
        return_value=mock_site,
    )
    return mock_site


# -- Unit tests (no live wiki connection needed) ---------------------------


class TestInitNoDomain:
    """Test that OswExpress raises TypeError when no domain is provided."""

    def test_no_domain_no_env_raises(self):
        with clean_env_vars(*ENV_VARS):
            with pytest.raises(TypeError, match="missing 1 required positional"):
                osw.express.OswExpress()


class TestInitInvalidDomain:
    """Test that OswExpress raises an error for invalid domain strings."""

    @pytest.mark.parametrize(
        "domain",
        [
            "not a domain!",
            "-starts-with-dash.com",
            "ends-with-dash-.com",
            "",
            "no_tld",
        ],
    )
    def test_invalid_domain_raises(self, domain):
        with clean_env_vars(*ENV_VARS):
            with pytest.raises((AssertionError, Exception)):
                osw.express.OswExpress(domain=domain)


class TestInitUnreachableDomain:
    """Test that OswExpress raises ConnectionError for unreachable domains."""

    def test_unreachable_domain_raises(self, mocker):
        """Mock requests.get to simulate unreachable domain."""
        with clean_env_vars(*ENV_VARS):
            cred_filepath = Path.cwd() / "test_unreachable_accounts.pwd.yaml"
            fake_domain = "unreachable.example.com"
            create_credentials_file(cred_filepath, fake_domain, "user", "pass")
            try:
                mocker.patch(
                    "osw.express.requests.get",
                    side_effect=ConnectionError("Mocked connection error"),
                )
                with pytest.raises(ConnectionError):
                    osw.express.OswExpress(
                        domain=fake_domain, cred_filepath=cred_filepath
                    )
            finally:
                if cred_filepath.exists():
                    cred_filepath.unlink()

    def test_unreachable_domain_non_200(self, mocker):
        """Mock requests.get to return a non-200 status code."""
        with clean_env_vars(*ENV_VARS):
            cred_filepath = Path.cwd() / "test_unreachable_accounts.pwd.yaml"
            fake_domain = "unreachable.example.com"
            create_credentials_file(cred_filepath, fake_domain, "user", "pass")
            try:
                mock_response = MagicMock()
                mock_response.status_code = 503
                mocker.patch("osw.express.requests.get", return_value=mock_response)
                with pytest.raises(ConnectionError, match="503"):
                    osw.express.OswExpress(
                        domain=fake_domain, cred_filepath=cred_filepath
                    )
            finally:
                if cred_filepath.exists():
                    cred_filepath.unlink()


class TestValidateDomain:
    """Test the domain validator directly."""

    @pytest.mark.parametrize(
        "domain,valid",
        [
            ("wiki-dev.open-semantic-lab.org", True),
            ("example.com", True),
            ("sub.domain.co.uk", True),
            ("not a domain!", False),
            ("-invalid.com", False),
            ("", False),
        ],
    )
    def test_validate_domain(self, domain, valid):
        if valid:
            result = osw.express.OswExpress.validate_domain(domain)
            assert result == domain
        else:
            with pytest.raises(AssertionError):
                osw.express.OswExpress.validate_domain(domain)


class TestInitEnvVarPriority:
    """Test that OSW_* env vars take priority over OSL_* env vars."""

    def test_osw_domain_takes_priority_over_osl(self, mocker):
        """When both OSW_WIKI_DOMAIN and OSL_WIKI_DOMAIN are set,
        OSW_WIKI_DOMAIN should be used."""
        with clean_env_vars(*ENV_VARS):
            osw_domain = "osw.example.com"
            osl_domain = "osl.example.com"
            os.environ["OSW_WIKI_DOMAIN"] = osw_domain
            os.environ["OSL_WIKI_DOMAIN"] = osl_domain

            cred_filepath = Path.cwd() / "test_priority_accounts.pwd.yaml"
            create_credentials_file(cred_filepath, osw_domain, "user", "pass")
            os.environ["OSW_CRED_FILEPATH"] = str(cred_filepath)

            try:
                # Mock requests.get so we don't need a live connection
                mock_response = MagicMock()
                mock_response.status_code = 200
                mocker.patch("osw.express.requests.get", return_value=mock_response)
                # Mock WtSite to avoid actual connection
                mock_wtsite(mocker)

                osw_obj = osw.express.OswExpress()
                assert osw_obj.domain == osw_domain
            finally:
                if cred_filepath.exists():
                    cred_filepath.unlink()

    def test_osl_domain_used_when_osw_absent(self, mocker):
        """When only OSL_WIKI_DOMAIN is set, it should be used."""
        with clean_env_vars(*ENV_VARS):
            osl_domain = "osl.example.com"
            os.environ["OSL_WIKI_DOMAIN"] = osl_domain

            cred_filepath = Path.cwd() / "test_osl_accounts.pwd.yaml"
            create_credentials_file(cred_filepath, osl_domain, "user", "pass")
            os.environ["OSL_CRED_FILEPATH"] = str(cred_filepath)

            try:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mocker.patch("osw.express.requests.get", return_value=mock_response)
                mock_wtsite(mocker)

                osw_obj = osw.express.OswExpress()
                assert osw_obj.domain == osl_domain
            finally:
                if cred_filepath.exists():
                    cred_filepath.unlink()

    def test_osw_cred_filepath_takes_priority_over_osl(self, mocker):
        """When both OSW_CRED_FILEPATH and OSL_CRED_FILEPATH are set,
        OSW_CRED_FILEPATH should be used."""
        with clean_env_vars(*ENV_VARS):
            domain = "priority.example.com"
            os.environ["OSW_WIKI_DOMAIN"] = domain

            osw_cred_fp = Path.cwd() / "test_osw_cred.pwd.yaml"
            osl_cred_fp = Path.cwd() / "test_osl_cred.pwd.yaml"
            create_credentials_file(osw_cred_fp, domain, "user", "pass")
            create_credentials_file(osl_cred_fp, domain, "user2", "pass2")
            os.environ["OSW_CRED_FILEPATH"] = str(osw_cred_fp)
            os.environ["OSL_CRED_FILEPATH"] = str(osl_cred_fp)

            try:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mocker.patch("osw.express.requests.get", return_value=mock_response)
                mock_wtsite(mocker)

                osw_obj = osw.express.OswExpress()
                assert osw_obj.cred_filepath == osw_cred_fp
            finally:
                for fp in [osw_cred_fp, osl_cred_fp]:
                    if fp.exists():
                        fp.unlink()


class TestInitCredFilepathFromCredMngr:
    """Test that cred_filepath from cred_mngr takes priority over the arg."""

    def test_cred_mngr_filepath_overrides_arg(self, mocker):
        with clean_env_vars(*ENV_VARS):
            domain = "mngr-override.example.com"
            arg_cred_fp = Path.cwd() / "test_arg_cred.pwd.yaml"
            mngr_cred_fp = Path.cwd() / "test_mngr_cred.pwd.yaml"
            create_credentials_file(arg_cred_fp, domain, "user_arg", "pass_arg")
            create_credentials_file(mngr_cred_fp, domain, "user_mngr", "pass_mngr")

            try:
                cred_mngr = CredentialManager(cred_filepath=mngr_cred_fp)

                mock_response = MagicMock()
                mock_response.status_code = 200
                mocker.patch("osw.express.requests.get", return_value=mock_response)
                mock_wtsite(mocker)

                osw_obj = osw.express.OswExpress(
                    domain=domain,
                    cred_filepath=arg_cred_fp,
                    cred_mngr=cred_mngr,
                )
                # cred_mngr's filepath should take priority
                assert osw_obj.cred_filepath == mngr_cred_fp
            finally:
                for fp in [arg_cred_fp, mngr_cred_fp]:
                    if fp.exists():
                        fp.unlink()


class TestContextManager:
    """Test OswExpress as a context manager."""

    def test_context_manager_enter_exit(self, mocker):
        with clean_env_vars(*ENV_VARS):
            domain = "ctx.example.com"
            cred_filepath = Path.cwd() / "test_ctx_accounts.pwd.yaml"
            create_credentials_file(cred_filepath, domain, "user", "pass")

            try:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mocker.patch("osw.express.requests.get", return_value=mock_response)
                mock_wtsite(mocker)

                osw_obj = osw.express.OswExpress(
                    domain=domain, cred_filepath=cred_filepath
                )
                # Test __enter__
                result = osw_obj.__enter__()
                assert result is osw_obj
            finally:
                if cred_filepath.exists():
                    cred_filepath.unlink()


# -- Live integration tests (require wiki credentials) ---------------------


class TestLiveInitFromEnvVarsOSL:
    """Test OswExpress initialization using OSL_* environment variables
    with a live wiki connection."""

    def test_live_init_from_osl_env_vars(
        self, wiki_domain, wiki_username, wiki_password
    ):
        """Set OSL_* env vars (not OSW_*) and verify connection works."""
        with clean_env_vars(*ENV_VARS):
            cred_filepath = Path.cwd() / "test_osl_live_accounts.pwd.yaml"
            create_credentials_file(
                cred_filepath, wiki_domain, wiki_username, wiki_password
            )
            os.environ["OSL_WIKI_DOMAIN"] = wiki_domain
            os.environ["OSL_CRED_FILEPATH"] = str(cred_filepath)

            try:
                osw_obj = osw.express.OswExpress()
                assert osw_obj.domain == wiki_domain
                assert osw_obj.site is not None
                assert osw_obj.cred_filepath == cred_filepath
                osw_obj.shut_down()
            finally:
                if cred_filepath.exists():
                    cred_filepath.unlink()

    def test_live_init_osl_cred_filepath(
        self, wiki_domain, wiki_username, wiki_password
    ):
        """Set OSL_CRED_FILEPATH (not OSW_CRED_FILEPATH) and verify it's used."""
        with clean_env_vars(*ENV_VARS):
            cred_filepath = Path.cwd() / "test_osl_cred_live.pwd.yaml"
            create_credentials_file(
                cred_filepath, wiki_domain, wiki_username, wiki_password
            )
            os.environ["OSL_CRED_FILEPATH"] = str(cred_filepath)

            try:
                osw_obj = osw.express.OswExpress(domain=wiki_domain)
                assert osw_obj.domain == wiki_domain
                assert osw_obj.cred_filepath == cred_filepath
                osw_obj.shut_down()
            finally:
                if cred_filepath.exists():
                    cred_filepath.unlink()


class TestLiveContextManager:
    """Test OswExpress as a context manager with a live wiki connection."""

    def test_live_context_manager(self, wiki_domain, wiki_username, wiki_password):
        cred_filepath = Path.cwd() / "test_ctx_live_accounts.pwd.yaml"
        create_credentials_file(
            cred_filepath, wiki_domain, wiki_username, wiki_password
        )
        try:
            with osw.express.OswExpress(
                domain=wiki_domain, cred_filepath=cred_filepath
            ) as osw_obj:
                assert osw_obj is not None
                assert osw_obj.domain == wiki_domain
                assert osw_obj.site is not None
        finally:
            if cred_filepath.exists():
                cred_filepath.unlink()


class TestLiveCredMngrOverride:
    """Test that cred_mngr.cred_filepath overrides the cred_filepath arg
    with a live wiki connection."""

    def test_live_cred_mngr_filepath_overrides_arg(
        self, wiki_domain, wiki_username, wiki_password
    ):
        arg_fp = Path.cwd() / "test_arg_live.pwd.yaml"
        mngr_fp = Path.cwd() / "test_mngr_live.pwd.yaml"
        create_credentials_file(arg_fp, wiki_domain, wiki_username, wiki_password)
        create_credentials_file(mngr_fp, wiki_domain, wiki_username, wiki_password)

        try:
            cred_mngr = CredentialManager(cred_filepath=mngr_fp)
            osw_obj = osw.express.OswExpress(
                domain=wiki_domain,
                cred_filepath=arg_fp,
                cred_mngr=cred_mngr,
            )
            assert osw_obj.cred_filepath == mngr_fp
            osw_obj.shut_down()
        finally:
            for fp in [arg_fp, mngr_fp]:
                if fp.exists():
                    fp.unlink()


# -- FileResult tests ------------------------------------------------------


class TestFileResult:
    """Test FileResult open/close/read/write and context manager."""

    def test_open_read_close(self, tmp_path):
        """Test opening, reading and closing a file via FileResult."""
        fp = tmp_path / "test.txt"
        fp.write_text("hello world")
        fr = FileResult(path=fp)

        # open
        fio = fr.open(mode="r")
        assert fio is not None
        assert not fio.closed
        content = fio.read()
        assert content == "hello world"

        # close
        fr.close()
        assert fio.closed

    def test_close_already_closed_warns(self, tmp_path):
        """Test that closing an already-closed file emits a warning."""
        fp = tmp_path / "test.txt"
        fp.write_text("data")
        fr = FileResult(path=fp)
        # Not opened yet - should warn
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            fr.close()
            assert len(w) == 1
            assert "already closed" in str(w[0].message).lower()

    def test_read_auto_opens(self, tmp_path):
        """Test that read() auto-opens the file if not opened."""
        fp = tmp_path / "test.txt"
        fp.write_text("auto open content")
        fr = FileResult(path=fp)
        content = fr.read()
        assert content == "auto open content"
        fr.close()

    def test_read_partial(self, tmp_path):
        """Test reading n characters."""
        fp = tmp_path / "test.txt"
        fp.write_text("abcdefghij")
        fr = FileResult(path=fp)
        content = fr.read(5)
        assert content == "abcde"
        fr.close()

    def test_write_auto_opens(self, tmp_path):
        """Test that write() auto-opens the file if not opened."""
        fp = tmp_path / "test.txt"
        fp.write_text("")
        fr = FileResult(path=fp)
        fr.write("written content")
        fr.close()
        assert fp.read_text() == "written content"

    def test_context_manager(self, tmp_path):
        """Test FileResult as a context manager."""
        fp = tmp_path / "test.txt"
        fp.write_text("ctx content")
        fr = FileResult(path=fp, mode="r")
        with fr as f:
            assert f is fr
            assert f.file_io is not None
            assert not f.file_io.closed
        # After exiting, file should be closed
        assert fr.file_io.closed

    def test_context_manager_delete_after_use(self, tmp_path):
        """Test FileResult context manager with delete_after_use=True."""
        fp = tmp_path / "test.txt"
        fp.write_text("delete me")
        fr = FileResult(path=fp, mode="r", delete_after_use=True)
        with fr:
            assert fp.exists()
        # After exiting, file should be deleted
        assert not fp.exists()

    def test_open_with_explicit_mode(self, tmp_path):
        """Test that explicit mode in open() overrides the attribute."""
        fp = tmp_path / "test.txt"
        fp.write_text("mode test")
        fr = FileResult(path=fp, mode="w")  # default mode is "w"
        # But open with "r" explicitly
        fio = fr.open(mode="r")
        content = fio.read()
        assert content == "mode test"
        fr.close()


# -- DownloadFileResult tests (validation, no live download) ----------------


class TestDownloadFileResultValidation:
    """Test DownloadFileResult __init__ validation paths without live wiki."""

    DOWNLOAD_ENV_VARS = ENV_VARS + ["OSW_DOWNLOAD_DIR", "OSL_DOWNLOAD_DIR"]

    def test_title_without_domain_raises(self):
        """When url_or_title is a plain title (no URL) and no domain env var
        is set, a ValueError should be raised."""
        with clean_env_vars(*self.DOWNLOAD_ENV_VARS):
            with pytest.raises(ValueError, match="Could not parse domain"):
                DownloadFileResult(
                    url_or_title="File:SomeFile.txt",
                    domain=None,
                )

    def _make_download_mocks(self, mocker, tmp_path):
        """Create mocks for DownloadFileResult that bypass actual download."""
        mock_osw = MagicMock(spec=osw.express.OswExpress)
        mock_entity = MagicMock()
        mock_wf = MagicMock()
        mock_lf = MagicMock()
        mock_lf.dict.return_value = {}
        mock_osw.load_entity.return_value = mock_entity
        mock_entity.cast.return_value = mock_wf
        mocker.patch(
            "osw.express.LocalFileController.from_other",
            return_value=mock_lf,
        )
        # Prevent put_from from actually writing bytes
        mocker.patch.object(DownloadFileResult, "put_from")
        # Provide cred_filepath so process_init_data won't call input()
        cred_fp = tmp_path / "test_cred.pwd.yaml"
        cred_fp.write_text("")
        return mock_osw, cred_fp

    def test_domain_parsed_from_url(self, tmp_path, mocker):
        """When url_or_title contains a URL, the domain should be parsed."""
        with clean_env_vars(*self.DOWNLOAD_ENV_VARS):
            mock_osw, cred_fp = self._make_download_mocks(mocker, tmp_path)
            url = "https://wiki.example.com/wiki/File:SomeFile.txt"
            target_fp = tmp_path / "SomeFile.txt"
            result = DownloadFileResult(
                url_or_title=url,
                osw_express=mock_osw,
                target_fp=target_fp,
                cred_filepath=cred_fp,
            )
            assert result.domain == "wiki.example.com"

    def test_domain_from_osw_env_var(self, tmp_path, mocker):
        """When url_or_title is a title and OSW_WIKI_DOMAIN is set."""
        with clean_env_vars(*self.DOWNLOAD_ENV_VARS):
            os.environ["OSW_WIKI_DOMAIN"] = "env.example.com"
            mock_osw, cred_fp = self._make_download_mocks(mocker, tmp_path)
            target_fp = tmp_path / "SomeFile.txt"
            result = DownloadFileResult(
                url_or_title="File:SomeFile.txt",
                osw_express=mock_osw,
                target_fp=target_fp,
                cred_filepath=cred_fp,
            )
            assert result.domain == "env.example.com"

    def test_domain_from_osl_env_var(self, tmp_path, mocker):
        """When url_or_title is a title and only OSL_WIKI_DOMAIN is set."""
        with clean_env_vars(*self.DOWNLOAD_ENV_VARS):
            os.environ["OSL_WIKI_DOMAIN"] = "osl-env.example.com"
            mock_osw, cred_fp = self._make_download_mocks(mocker, tmp_path)
            target_fp = tmp_path / "SomeFile.txt"
            result = DownloadFileResult(
                url_or_title="File:SomeFile.txt",
                osw_express=mock_osw,
                target_fp=target_fp,
                cred_filepath=cred_fp,
            )
            assert result.domain == "osl-env.example.com"

    def test_target_dir_from_osw_env_var(self, tmp_path, mocker):
        """When OSW_DOWNLOAD_DIR is set, it should be used as target_dir."""
        with clean_env_vars(*self.DOWNLOAD_ENV_VARS):
            os.environ["OSW_WIKI_DOMAIN"] = "env.example.com"
            download_dir = str(tmp_path / "downloads")
            os.environ["OSW_DOWNLOAD_DIR"] = download_dir
            mock_osw, cred_fp = self._make_download_mocks(mocker, tmp_path)
            result = DownloadFileResult(
                url_or_title="File:SomeFile.txt",
                osw_express=mock_osw,
                cred_filepath=cred_fp,
            )
            assert result.target_dir == Path(download_dir)

    def test_target_dir_from_osl_env_var(self, tmp_path, mocker):
        """When only OSL_DOWNLOAD_DIR is set, it should be used."""
        with clean_env_vars(*self.DOWNLOAD_ENV_VARS):
            os.environ["OSW_WIKI_DOMAIN"] = "env.example.com"
            download_dir = str(tmp_path / "osl_downloads")
            os.environ["OSL_DOWNLOAD_DIR"] = download_dir
            mock_osw, cred_fp = self._make_download_mocks(mocker, tmp_path)
            result = DownloadFileResult(
                url_or_title="File:SomeFile.txt",
                osw_express=mock_osw,
                cred_filepath=cred_fp,
            )
            assert result.target_dir == Path(download_dir)

    def test_use_cached_with_existing_file(self, tmp_path):
        """When use_cached=True and the file already exists, no download."""
        with clean_env_vars(*self.DOWNLOAD_ENV_VARS):
            cached_file = tmp_path / "cached.txt"
            cached_file.write_text("cached content")
            cred_fp = tmp_path / "test_cred.pwd.yaml"
            cred_fp.write_text("")

            result = DownloadFileResult(
                url_or_title="File:cached.txt",
                use_cached=True,
                target_fp=cached_file,
                domain="cached.example.com",
                cred_filepath=cred_fp,
            )
            assert result.path == cached_file
            assert result.use_cached is True

    def test_target_fn_derived_from_title(self, tmp_path, mocker):
        """The target filename should be derived from the title after 'File:'."""
        with clean_env_vars(*self.DOWNLOAD_ENV_VARS):
            os.environ["OSW_WIKI_DOMAIN"] = "env.example.com"
            mock_osw, cred_fp = self._make_download_mocks(mocker, tmp_path)
            result = DownloadFileResult(
                url_or_title="File:MyDocument.pdf",
                osw_express=mock_osw,
                target_dir=tmp_path,
                cred_filepath=cred_fp,
            )
            assert result.target_fn == "MyDocument.pdf"


# -- UploadFileResult tests (validation, no live upload) --------------------


class TestUploadFileResultValidation:
    """Test UploadFileResult __init__ validation paths without live wiki."""

    def test_source_file_not_found_raises(self, tmp_path):
        """Passing a non-existent file path should raise FileNotFoundError."""
        nonexistent = tmp_path / "nonexistent.txt"
        with pytest.raises(FileNotFoundError):
            UploadFileResult(source=nonexistent)

    def test_source_is_directory_raises(self, tmp_path):
        """Passing a directory as source should raise IsADirectoryError."""
        with pytest.raises(IsADirectoryError):
            UploadFileResult(source=tmp_path)

    def test_url_or_title_without_file_namespace_raises(self, tmp_path):
        """url_or_title without 'File:' namespace should raise ValueError."""
        source_file = tmp_path / "test.txt"
        source_file.write_text("data")
        with pytest.raises(ValueError, match="namespace 'File'"):
            UploadFileResult(
                source=source_file,
                url_or_title="NoFileNamespace.txt",
            )

    def test_target_fpt_mismatch_raises(self, tmp_path):
        """Mismatched target_fpt and url_or_title should raise ValueError."""
        source_file = tmp_path / "test.txt"
        source_file.write_text("data")
        with pytest.raises(ValueError, match="does not match"):
            UploadFileResult(
                source=source_file,
                url_or_title="File:FileA.txt",
                target_fpt="File:FileB.txt",
            )

    def test_domain_mismatch_in_url_raises(self, tmp_path):
        """Domain in url_or_title not matching domain arg should raise."""
        source_file = tmp_path / "test.txt"
        source_file.write_text("data")
        with pytest.raises(ValueError, match="does not match"):
            UploadFileResult(
                source=source_file,
                url_or_title="https://wiki-a.example.com/wiki/File:test.txt",
                domain="wiki-b.example.com",
            )

    def test_fpt_without_domain_or_osw_raises(self, tmp_path):
        """url_or_title as title without domain or osw_express should raise."""
        with clean_env_vars(*ENV_VARS):
            source_file = tmp_path / "test.txt"
            source_file.write_text("data")
            with pytest.raises(ValueError, match="domain"):
                UploadFileResult(
                    source=source_file,
                    url_or_title="File:test.txt",
                )


# -- import_with_fallback tests --------------------------------------------


class TestImportWithFallback:
    """Test import_with_fallback function."""

    def test_successful_import_from_list(self):
        """When the module and class exist, they should be imported."""
        caller_globals = {}
        import_with_fallback(
            [
                DataModel(
                    module="osw.controller.file.base",
                    class_name="FileController",
                )
            ],
            caller_globals,
        )
        from osw.controller.file.base import FileController

        assert caller_globals["FileController"] is FileController

    def test_successful_import_from_dict(self):
        """When passing a dict, it should derive DataModels and import."""
        caller_globals = {}
        # CredentialManager exists in osw.auth
        import_with_fallback(
            [
                DataModel(
                    module="osw.auth",
                    class_name="CredentialManager",
                )
            ],
            caller_globals,
        )
        assert caller_globals["CredentialManager"] is CredentialManager

    def test_dict_input_uses_default_module(self):
        """When to_import is a dict without explicit module, default to
        osw.model.entity."""
        caller_globals = {}
        # Item exists in osw.model.entity
        import_with_fallback(
            {"Item": "Category:Item"},
            caller_globals,
        )
        import osw.model.entity as model

        assert caller_globals["Item"] is model.Item

    def test_dict_input_with_custom_module(self):
        """When to_import is a dict with explicit module, use it."""
        caller_globals = {}
        import_with_fallback(
            {"CredentialManager": None},
            caller_globals,
            module="osw.auth",
        )
        assert caller_globals["CredentialManager"] is CredentialManager

    def test_none_to_import_raises(self):
        """Passing None should raise ValueError."""
        with pytest.raises(ValueError, match="to_import"):
            import_with_fallback(None, {})

    def test_nonexistent_class_no_deps_raises(self):
        """When the class doesn't exist and no dependencies or osw_fpt
        are given, should raise AttributeError."""
        caller_globals = {}
        with pytest.raises(AttributeError, match="could not be derived"):
            import_with_fallback(
                [
                    DataModel(
                        module="osw.model.entity",
                        class_name="NonExistentClass9999",
                    )
                ],
                caller_globals,
            )


class TestDataModel:
    """Test the DataModel class."""

    def test_create_data_model(self):
        dm = DataModel(
            module="osw.model.entity",
            class_name="Item",
            osw_fpt="Category:Item",
        )
        assert dm.module == "osw.model.entity"
        assert dm.class_name == "Item"
        assert dm.osw_fpt == "Category:Item"

    def test_data_model_defaults(self):
        dm = DataModel(module="osw.model.entity", class_name="Item")
        assert dm.osw_fpt is None
