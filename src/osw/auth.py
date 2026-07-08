from __future__ import annotations

import getpass
import os
import warnings
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union

import yaml
from oold.backend.auth import UserPwdCredential as _OoldUserPwdCredential
from oold.backend.auth import find_credential as _find_credential
from oold.backend.auth import load_credentials as _load_credentials
from opensemantic.v1 import OswBaseModel
from pydantic.v1 import PrivateAttr

from osw.defaults import paths as default_paths


def _secret_to_str(v):
    """Unwrap SecretStr to plain str, pass through otherwise."""
    if hasattr(v, "get_secret_value"):
        return v.get_secret_value()
    return v


class CredentialManager(OswBaseModel):
    """Handles credentials.

    Delegates YAML loading and IRI matching to oold.backend.auth,
    adding osw-specific features (default paths, .gitignore management).
    Remains a v1 model because WtSiteConfig (v1) uses it as a field.
    """

    cred_filepath: Optional[Union[Union[str, Path], List[Union[str, Path]]]] = None
    """Filepath to yaml file with credentials for osw and connected services"""
    cert_filepath: Optional[Union[Union[str, Path], List[Union[str, Path]]]] = None
    """Filepath to the certificates for osw and connected services"""

    _credentials: List[CredentialManager.BaseCredential] = PrivateAttr([])
    """in memory credential store"""

    class BaseCredential(OswBaseModel):
        """Abstract base class for credentials"""

        iri: str
        """the iri the credential is valid for"""

    class UserPwdCredential(BaseCredential):
        """a username - password credential"""

        username: str
        """the user identifier"""
        password: str
        """the users password"""

    class OAuth1Credential(BaseCredential):
        """OAuth1 credentials. See
        https://requests-oauthlib.readthedocs.io/en/latest/oauth1_workflow.html"""

        consumer_token: str
        """consumer token"""
        consumer_secret: str
        """consumer secret """
        access_token: str
        """access token"""
        access_secret: str
        """access secret"""

    class CredentialFallback(Enum):
        """Modes of handling missing credentials

        Attributes
        ----------
        none:
            throw error
        ask:
            use getpass to ask for credentials
        """

        ask = "ask"  # use getpass to ask for credentials
        none = "none"  # throw error

    class CredentialConfig(OswBaseModel):
        """Reads credentials from a yaml file"""

        iri: str
        """internationalized resource identifier / address of the service, may contain
        protocol, domain, port and path matches by "contains" returning the shortest
        match"""
        fallback: Optional[CredentialManager.CredentialFallback] = "none"
        """The fallback strategy if no credential was found for the given origin"""

    def __init__(self, **data):
        super().__init__(**data)
        if self.cred_filepath:
            if not isinstance(self.cred_filepath, list):
                self.cred_filepath = [self.cred_filepath]
            self.cred_filepath = [Path(fp) for fp in self.cred_filepath if fp != ""]

    @staticmethod
    def _oold_to_osw(oold_cred) -> CredentialManager.BaseCredential:
        """Convert an oold BaseCredential to an osw credential (plain str passwords)."""
        from oold.backend.auth import OAuth1Credential as _OoldOAuth1

        if isinstance(oold_cred, _OoldOAuth1):
            return CredentialManager.OAuth1Credential(
                iri=oold_cred.iri,
                consumer_token=oold_cred.consumer_token,
                consumer_secret=_secret_to_str(oold_cred.consumer_secret),
                access_token=oold_cred.access_token,
                access_secret=_secret_to_str(oold_cred.access_secret),
            )
        if isinstance(oold_cred, _OoldUserPwdCredential):
            return CredentialManager.UserPwdCredential(
                iri=oold_cred.iri,
                username=oold_cred.username,
                password=_secret_to_str(oold_cred.password),
            )
        return CredentialManager.BaseCredential(iri=oold_cred.iri)

    def _load_file_credentials(self):
        """Load credentials from YAML files using oold, return as dict."""
        all_creds = {}
        if self.cred_filepath:
            for fp in self.cred_filepath:
                fp = Path(fp)
                if not fp.exists():
                    continue
                try:
                    loaded = _load_credentials(fp, into_store=False)
                    all_creds.update(loaded)
                except Exception as exc:
                    print(exc)
        return all_creds

    def get_credential(self, config: CredentialConfig) -> BaseCredential:
        """Reads credentials from a yaml file or the in memory store.

        Uses oold.backend.auth.find_credential for IRI matching.

        Parameters
        ----------
        config:
            see CredentialConfig

        Returns
        -------
        credential :
            Credential, contain attributes 'username' and 'password' and
            the matching iri.
        """
        oold_creds = self._load_file_credentials()

        for osw_cred in self._credentials:
            oold_creds[osw_cred.iri] = osw_cred

        match = _find_credential(config.iri, oold_creds)

        if match is not None:
            if isinstance(match, CredentialManager.BaseCredential):
                return match
            return self._oold_to_osw(match)

        # Environment variables (e.g. loaded from a .env file) come before
        # any interactive fallback; credentials are kept in memory only.
        username = os.getenv("OSW_USERNAME") or os.getenv("OSL_USERNAME")
        password = os.getenv("OSW_PASSWORD") or os.getenv("OSL_PASSWORD")
        if username is not None and password is not None:
            cred = CredentialManager.UserPwdCredential(
                username=username, password=password, iri=config.iri
            )
            self.add_credential(cred)
            return cred

        if config.fallback is CredentialManager.CredentialFallback.ask:
            if self.cred_filepath:
                filepath_str = "', '".join([str(fp) for fp in self.cred_filepath])
                print(
                    f"No credentials for {config.iri} found in path '{filepath_str}'. "
                    f"Please use the prompt to login"
                )
            username = input("Enter username: ")
            password = getpass.getpass("Enter password: ")
            cred = CredentialManager.UserPwdCredential(
                username=username, password=password, iri=config.iri
            )
            # kept in memory only; persisting credentials to a file happens
            # exclusively through an explicit save_credentials_to_file() call
            self.add_credential(cred)
            return cred

        return None

    def add_credential(self, cred: BaseCredential):
        """adds a credential to the in memory store

        Parameters
        ----------
        cred
            the credential to add
        """
        self._credentials.append(cred)

    def iri_in_credentials(self, iri: str) -> bool:
        """checks if a credential for a given iri exists

        Parameters
        ----------
        iri
            the iri to check

        Returns
        -------
        bool
            True if a credential exists for the given iri
        """
        return any(cred.iri == iri for cred in self._credentials)

    def iri_in_file(self, iri: str) -> bool:
        """checks if a credential for a given iri exists in the file

        Parameters
        ----------
        iri
            the iri to check

        Returns
        -------
        bool
            True if a credential exists for the given iri
        """
        if self.cred_filepath:
            for fp in self.cred_filepath:
                if fp != "":
                    if Path(fp).exists():
                        with open(fp, encoding="utf-8") as stream:
                            try:
                                accounts = yaml.safe_load(stream)
                                if accounts is None:
                                    continue
                                for iri_ in accounts.keys():
                                    if iri_ == iri:
                                        return True
                            except yaml.YAMLError as exc:
                                print(exc)
        return False

    def save_credentials_to_file(
        self,
        filepath: Union[str, Path] = None,
        set_cred_filepath: bool = False,
    ):
        """Saves the in memory credentials to a file

        Parameters
        ----------
        filepath
            The filepath to save the credentials to. If None, the filepath specified
            in the CredentialManager is used.  If cred_filepath and filepath are None,
            the default path is used. If the file does not exist, it is created.
        set_cred_filepath
            If True, the cred_filepath is set to the given filepath. If False, the
            cred_filepath of the CredentialManager is not changed.
        """
        warnings.warn(
            "save_credentials_to_file() writes credentials to disk in clear "
            "text and is deprecated. Prefer environment variables (e.g. via "
            "a .env file) or in-memory credentials.",
            DeprecationWarning,
            stacklevel=2,
        )
        cred_filepaths = [filepath]
        if filepath is None:
            cred_filepaths = self.cred_filepath
            if self.cred_filepath is None:
                cred_filepaths = [default_paths.cred_filepath]
        if set_cred_filepath:
            self.cred_filepath = cred_filepaths
        for fp in cred_filepaths:
            file = Path(fp)
            if not file.parent.exists():
                file.parent.mkdir(parents=True)
            data = {}
            file_already_exists = file.exists()
            if file_already_exists:
                data = yaml.safe_load(file.read_text(encoding="utf-8"))
                if data is None:
                    data = {}
            for cred in self._credentials:
                data[cred.iri] = cred.dict(exclude={"iri"})
            with open(fp, "w", encoding="utf-8") as stream:
                yaml.dump(data, stream)
            if file_already_exists:
                print(f"Credentials file updated at '{fp.resolve()}'.")
            else:
                print(f"Credentials file created at '{fp.resolve()}'.")


CredentialManager.CredentialConfig.update_forward_refs()
