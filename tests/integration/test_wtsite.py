"""Tests for WtSite session renewal / token recovery mechanism.

These tests cover the `try_and_renew_token` decorators on both WtSite and WtPage,
and the `_relogin()` method used when sessions expire.

Three recovery layers exist:
1. WtSite.try_and_renew_token: catches APIError -> CSRF refresh -> _relogin()
2. WtPage.try_and_renew_token: same pattern, accesses wtSite._relogin()
3. WtPage.edit(): own retry loop (not tested here - relies on the same primitives)

Run unit tests only (no live wiki):
    pytest tests/integration/test_wtsite.py -k "not Live" -v

Run all tests with live wiki:
    tox -e test -- tests/integration/test_wtsite.py
        --wiki_domain <domain> --wiki_username <user> --wiki_password <pass>
"""

from pathlib import Path
from unittest.mock import MagicMock

import mwclient.errors
import pytest
import yaml

import osw.express
from osw.auth import CredentialManager
from osw.wtsite import WtPage, WtSite

# -- Helpers ---------------------------------------------------------------


def create_credentials_file(
    cred_filepath: Path, wiki_domain: str, wiki_username: str, wiki_password: str
):
    cred_filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(cred_filepath, "w") as file:
        yaml.dump(
            {wiki_domain: {"username": wiki_username, "password": wiki_password}}, file
        )


def make_api_error(code="badtoken", info="Invalid CSRF token"):
    """Create an mwclient APIError."""
    return mwclient.errors.APIError(code, info, {})


# -- Unit tests: WtSite.try_and_renew_token decorator ---------------------


class TestWtSiteDecoratorSuccess:
    """Test that decorated methods succeed on first call without recovery."""

    def test_wtsite_decorator_succeeds_on_first_call(self, mocker):
        mock_mw_site = MagicMock()

        wt_site = WtSite.__new__(WtSite)
        wt_site._site = mock_mw_site
        wt_site._cred_mngr = None
        wt_site._iri = "token-ok.example.com"
        wt_site._page_cache = {}
        wt_site._cache_enabled = False

        @WtSite.try_and_renew_token
        def succeeding_method(self_):
            return "success"

        result = succeeding_method(wt_site)
        assert result == "success"
        # No token refresh should have been called
        mock_mw_site.get_token.assert_not_called()


class TestWtSiteDecoratorCsrfRecovery:
    """Test that the WtSite decorator recovers via CSRF token refresh."""

    def test_wtsite_decorator_recovers_with_csrf_refresh(self, mocker):
        mock_mw_site = MagicMock()
        mock_cred_mngr = MagicMock(spec=CredentialManager)
        mock_cred = MagicMock(spec=CredentialManager.UserPwdCredential)
        mock_cred.username = "user"
        mock_cred.password = "pass"
        mock_cred_mngr.get_credential.return_value = mock_cred

        # Bypass __init__ to avoid isinstance checks on credentials
        wt_site = WtSite.__new__(WtSite)
        wt_site._site = mock_mw_site
        wt_site._cred_mngr = mock_cred_mngr
        wt_site._iri = "csrf-refresh.example.com"
        wt_site._page_cache = {}
        wt_site._cache_enabled = False

        # Set up a decorated method to fail once then succeed
        call_count = 0

        @WtSite.try_and_renew_token
        def flaky_method(self_):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise make_api_error()
            return "success"

        result = flaky_method(wt_site)
        assert result == "success"
        assert call_count == 2
        # CSRF refresh should have been called
        mock_mw_site.get_token.assert_called_once_with("csrf", force=True)


class TestWtSiteDecoratorReloginRecovery:
    """Test that the WtSite decorator falls back to full _relogin()."""

    def test_wtsite_decorator_recovers_with_relogin(self, mocker):
        mock_mw_site = MagicMock()
        mock_cred_mngr = MagicMock(spec=CredentialManager)
        mock_cred = MagicMock(spec=CredentialManager.UserPwdCredential)
        mock_cred.username = "user"
        mock_cred.password = "pass"
        mock_cred_mngr.get_credential.return_value = mock_cred

        wt_site = WtSite.__new__(WtSite)
        wt_site._site = mock_mw_site
        wt_site._cred_mngr = mock_cred_mngr
        wt_site._iri = "relogin.example.com"
        wt_site._page_cache = {}
        wt_site._cache_enabled = False

        # CSRF refresh itself raises APIError -> triggers _relogin
        mock_mw_site.get_token.side_effect = make_api_error()

        call_count = 0

        @WtSite.try_and_renew_token
        def flaky_method(self_):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise make_api_error()
            return "success"

        spy_relogin = mocker.patch.object(wt_site, "_relogin")

        result = flaky_method(wt_site)
        assert result == "success"
        # Call 1: fails -> CSRF refresh fails -> _relogin -> Call 2: succeeds
        assert call_count == 2
        spy_relogin.assert_called_once()


class TestWtSiteDecoratorAllFail:
    """Test that the decorator propagates the error when all retries fail."""

    def test_wtsite_decorator_raises_after_all_retries_fail(self, mocker):
        mock_mw_site = MagicMock()
        mock_cred_mngr = MagicMock(spec=CredentialManager)
        mock_cred = MagicMock(spec=CredentialManager.UserPwdCredential)
        mock_cred.username = "user"
        mock_cred.password = "pass"
        mock_cred_mngr.get_credential.return_value = mock_cred

        wt_site = WtSite.__new__(WtSite)
        wt_site._site = mock_mw_site
        wt_site._cred_mngr = mock_cred_mngr
        wt_site._iri = "all-fail.example.com"
        wt_site._page_cache = {}
        wt_site._cache_enabled = False

        # CSRF refresh also fails
        mock_mw_site.get_token.side_effect = make_api_error()
        # _relogin succeeds but the function keeps failing
        mocker.patch.object(wt_site, "_relogin")

        @WtSite.try_and_renew_token
        def always_fails(self_):
            raise make_api_error()

        with pytest.raises(mwclient.errors.APIError):
            always_fails(wt_site)


# -- Unit tests: WtPage.try_and_renew_token decorator ---------------------


class TestWtPageDecoratorCsrfRecovery:
    """Test that the WtPage decorator recovers via CSRF token refresh."""

    def test_wtpage_decorator_recovers_with_csrf_refresh(self, mocker):
        mock_mw_site = MagicMock()
        mock_cred_mngr = MagicMock(spec=CredentialManager)
        mock_cred = MagicMock(spec=CredentialManager.UserPwdCredential)
        mock_cred.username = "user"
        mock_cred.password = "pass"
        mock_cred_mngr.get_credential.return_value = mock_cred

        wt_site = WtSite.__new__(WtSite)
        wt_site._site = mock_mw_site
        wt_site._cred_mngr = mock_cred_mngr
        wt_site._iri = "page-csrf.example.com"
        wt_site._page_cache = {}
        wt_site._cache_enabled = False

        # Create a WtPage without initializing from wiki
        page = WtPage(wtSite=wt_site, title="Test:Page", do_init=False)

        call_count = 0

        @WtPage.try_and_renew_token
        def flaky_page_method(self_):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise make_api_error()
            return "page_success"

        result = flaky_page_method(page)
        assert result == "page_success"
        assert call_count == 2
        # CSRF refresh goes through wtSite._site
        mock_mw_site.get_token.assert_called_once_with("csrf", force=True)


class TestWtPageDecoratorReloginRecovery:
    """Test that the WtPage decorator falls back to wtSite._relogin()."""

    def test_wtpage_decorator_recovers_with_relogin(self, mocker):
        mock_mw_site = MagicMock()
        mock_cred_mngr = MagicMock(spec=CredentialManager)
        mock_cred = MagicMock(spec=CredentialManager.UserPwdCredential)
        mock_cred.username = "user"
        mock_cred.password = "pass"
        mock_cred_mngr.get_credential.return_value = mock_cred

        wt_site = WtSite.__new__(WtSite)
        wt_site._site = mock_mw_site
        wt_site._cred_mngr = mock_cred_mngr
        wt_site._iri = "page-relogin.example.com"
        wt_site._page_cache = {}
        wt_site._cache_enabled = False

        # CSRF refresh also raises
        mock_mw_site.get_token.side_effect = make_api_error()

        page = WtPage(wtSite=wt_site, title="Test:Page", do_init=False)

        call_count = 0

        @WtPage.try_and_renew_token
        def flaky_page_method(self_):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise make_api_error()
            return "page_relogin_success"

        spy_relogin = mocker.patch.object(wt_site, "_relogin")

        result = flaky_page_method(page)
        assert result == "page_relogin_success"
        # Call 1: fails -> CSRF refresh fails -> _relogin -> Call 2: succeeds
        assert call_count == 2
        spy_relogin.assert_called_once()


# -- Unit tests: _relogin() edge cases ------------------------------------


class TestReloginLegacyConfig:
    """Test that _relogin() raises RuntimeError for legacy config."""

    def test_relogin_raises_for_legacy_config(self, mocker):
        mock_mw_site = MagicMock()
        mocker.patch("osw.wtsite.mwclient.Site", return_value=mock_mw_site)

        wt_site = WtSite.__new__(WtSite)
        wt_site._cred_mngr = None
        wt_site._iri = None
        wt_site._site = mock_mw_site
        wt_site._page_cache = {}
        wt_site._cache_enabled = False

        with pytest.raises(RuntimeError, match="Cannot re-login"):
            wt_site._relogin()


class TestReloginNonUserPwdCredentials:
    """Test that _relogin() raises RuntimeError for non-UserPwd credentials."""

    def test_relogin_raises_for_non_userpwd_credentials(self, mocker):
        mock_mw_site = MagicMock()
        mock_cred_mngr = MagicMock(spec=CredentialManager)
        # Return an OAuth1 credential instead of UserPwd
        mock_oauth_cred = MagicMock(spec=CredentialManager.OAuth1Credential)
        mock_cred_mngr.get_credential.return_value = mock_oauth_cred

        wt_site = WtSite.__new__(WtSite)
        wt_site._cred_mngr = mock_cred_mngr
        wt_site._iri = "oauth.example.com"
        wt_site._site = mock_mw_site
        wt_site._page_cache = {}
        wt_site._cache_enabled = False

        with pytest.raises(RuntimeError, match="only supported for username/password"):
            wt_site._relogin()


class TestReloginCallsSiteLogin:
    """Test that _relogin() calls _site.login() with correct credentials."""

    def test_relogin_calls_site_login_with_stored_credentials(self, mocker):
        mock_mw_site = MagicMock()
        mock_cred_mngr = MagicMock(spec=CredentialManager)
        mock_cred = MagicMock(spec=CredentialManager.UserPwdCredential)
        mock_cred.username = "TestUser"
        mock_cred.password = "TestPass"
        mock_cred_mngr.get_credential.return_value = mock_cred

        wt_site = WtSite.__new__(WtSite)
        wt_site._cred_mngr = mock_cred_mngr
        wt_site._iri = "login-test.example.com"
        wt_site._site = mock_mw_site
        wt_site._page_cache = {}
        wt_site._cache_enabled = False

        wt_site._relogin()

        mock_mw_site.login.assert_called_once_with(
            username="TestUser", password="TestPass"
        )


# -- Live integration tests (require wiki credentials) --------------------


class TestLiveRecoveryFromInvalidCsrfToken:
    """Test recovery when the CSRF token is invalidated."""

    def test_live_recovery_from_invalid_csrf_token(
        self, wiki_domain, wiki_username, wiki_password
    ):
        cred_filepath = Path.cwd() / "test_csrf_recovery_accounts.pwd.yaml"
        create_credentials_file(
            cred_filepath, wiki_domain, wiki_username, wiki_password
        )
        try:
            osw_obj = osw.express.OswExpress(
                domain=wiki_domain, cred_filepath=cred_filepath
            )
            wt_site = osw_obj.site

            # Verify connection works first
            result = wt_site.get_page(
                WtSite.GetPageParam(titles=["Main_Page"], raise_warning=False)
            )
            assert result is not None

            # Sabotage: overwrite the CSRF token with garbage
            wt_site._site.tokens["csrf"] = "INVALID_TOKEN_12345"

            # This should trigger the try_and_renew_token decorator's
            # CSRF refresh path and recover
            result2 = wt_site.get_page(
                WtSite.GetPageParam(titles=["Main_Page"], raise_warning=False)
            )
            assert result2 is not None

            osw_obj.shut_down()
        finally:
            if cred_filepath.exists():
                cred_filepath.unlink()


class TestLiveRecoveryFromExpiredSession:
    """Test recovery when session cookies are cleared (simulating session expiry)."""

    def test_live_recovery_from_expired_session(
        self, wiki_domain, wiki_username, wiki_password
    ):
        cred_filepath = Path.cwd() / "test_session_recovery_accounts.pwd.yaml"
        create_credentials_file(
            cred_filepath, wiki_domain, wiki_username, wiki_password
        )
        try:
            osw_obj = osw.express.OswExpress(
                domain=wiki_domain, cred_filepath=cred_filepath
            )
            wt_site = osw_obj.site

            # Verify connection works first
            result = wt_site.get_page(
                WtSite.GetPageParam(titles=["Main_Page"], raise_warning=False)
            )
            assert result is not None

            # Sabotage: clear all session cookies to simulate session expiry
            wt_site._site.connection.cookies.clear()

            # This should trigger the decorator's _relogin() path and recover
            result2 = wt_site.get_page(
                WtSite.GetPageParam(titles=["Main_Page"], raise_warning=False)
            )
            assert result2 is not None

            osw_obj.shut_down()
        finally:
            if cred_filepath.exists():
                cred_filepath.unlink()


class TestLiveCascadingRecovery:
    """Test recovery when both CSRF token AND session cookies are corrupted."""

    def test_live_cascading_recovery(self, wiki_domain, wiki_username, wiki_password):
        cred_filepath = Path.cwd() / "test_cascade_recovery_accounts.pwd.yaml"
        create_credentials_file(
            cred_filepath, wiki_domain, wiki_username, wiki_password
        )
        try:
            osw_obj = osw.express.OswExpress(
                domain=wiki_domain, cred_filepath=cred_filepath
            )
            wt_site = osw_obj.site

            # Verify connection works first
            result = wt_site.get_page(
                WtSite.GetPageParam(titles=["Main_Page"], raise_warning=False)
            )
            assert result is not None

            # Sabotage both: corrupt CSRF token AND clear session cookies
            wt_site._site.tokens["csrf"] = "INVALID_TOKEN_12345"
            wt_site._site.connection.cookies.clear()

            # This should cascade: CSRF refresh fails -> _relogin() succeeds
            result2 = wt_site.get_page(
                WtSite.GetPageParam(titles=["Main_Page"], raise_warning=False)
            )
            assert result2 is not None

            osw_obj.shut_down()
        finally:
            if cred_filepath.exists():
                cred_filepath.unlink()
