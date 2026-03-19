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
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, create_autospec

import pytest
import yaml

import osw.express
from osw.auth import CredentialManager
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
