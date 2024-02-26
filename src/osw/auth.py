from __future__ import annotations

import getpass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union

import yaml
from pydantic.v1 import FilePath, PrivateAttr

from osw.model.static import OswBaseModel


class CredentialManager(OswBaseModel):
    """Handles credentials"""

    cred_filepath: Optional[Union[Union[str, FilePath], List[Union[str, FilePath]]]]
    """Filepath to yaml file with credentials for osw and connected services"""
    cert_filepath: Optional[Union[Union[str, FilePath], List[Union[str, FilePath]]]]
    """Filepath to the certificates for osw and connected services"""

    _credentials: List[BaseCredential] = PrivateAttr([])
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
        """OAuth1 credentials. See https://requests-oauthlib.readthedocs.io/en/latest/oauth1_workflow.html"""

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

    def get_credential(self, config: CredentialConfig) -> BaseCredential:
        """Reads credentials from a yaml file or the in memory store

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

        _file_credentials: List[CredentialManager.BaseCredential] = []
        if self.cred_filepath:
            filepaths = self.cred_filepath
            if type(filepaths) is not list:
                filepaths = [filepaths]

            for filepath in filepaths:
                if filepath != "":
                    with open(filepath, "r") as stream:
                        try:
                            accounts = yaml.safe_load(stream)
                            if accounts is None:  # Catch empty file
                                continue
                            for iri in accounts.keys():
                                if (
                                    "username" in accounts[iri]
                                    and "password" in accounts[iri]
                                ):
                                    cred = CredentialManager.UserPwdCredential(
                                        username=accounts[iri]["username"],
                                        password=accounts[iri]["password"],
                                        iri=iri,
                                    )
                                    _file_credentials.append(cred)
                                if (
                                    "consumer_token" in accounts[iri]
                                    and "consumer_secret" in accounts[iri]
                                    and "access_token" in accounts[iri]
                                    and "access_secret" in accounts[iri]
                                ):
                                    cred = CredentialManager.OAuth1Credential(
                                        consumer_token=accounts[iri]["consumer_token"],
                                        consumer_secret=accounts[iri][
                                            "consumer_secret"
                                        ],
                                        access_token=accounts[iri]["access_token"],
                                        access_secret=accounts[iri]["access_secret"],
                                        iri=iri,
                                    )
                                    _file_credentials.append(cred)
                        except yaml.YAMLError as exc:
                            print(exc)

        match_iri = ""
        cred = None
        creds = _file_credentials + self._credentials
        for _cred in creds:
            iri = _cred.iri
            if config.iri in iri:
                if match_iri == "" or len(match_iri) > len(
                    iri
                ):  # use the less specific match
                    match_iri = iri
                    cred = _cred

        if cred is None:
            if config.fallback is CredentialManager.CredentialFallback.ask:
                print(
                    f"No credentials for {config.iri} found. "
                    f"Please use the prompt to login"
                )
                username = input("Enter username: ")
                password = getpass.getpass("Enter password: ")
                cred = CredentialManager.UserPwdCredential(
                    username=username, password=password, iri=config.iri
                )
        return cred

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
        for cred in self._credentials:
            if cred.iri == iri:
                return True
        return False

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
            if not self.cred_filepath.exists():
                return False
            filepaths = self.cred_filepath
            if type(filepaths) is not list:
                filepaths = [filepaths]

            for filepath in filepaths:
                if filepath != "":
                    with open(filepath, "r") as stream:
                        try:
                            accounts = yaml.safe_load(stream)
                            if accounts is None:  # Catch empty file
                                continue
                            for iri_ in accounts.keys():
                                if iri_ == iri:
                                    return True
                        except yaml.YAMLError as exc:
                            print(exc)
        return False

    def save_credentials_to_file(
        self,
        filepath: Union[str, FilePath] = None,
    ):
        """saves the in memory credentials to a file

        Parameters
        ----------
        filepath
            The filepath to save the credentials to. If None, the filepath specified
            in the CredentialManager is used. If specified, the cred_filepath of the
            CredentialManager is updated.
        """
        if filepath is None:
            filepath = self.cred_filepath
        else:
            self.cred_filepath = filepath
        file = Path(filepath)
        if not file.parent.exists():
            file.parent.mkdir(parents=True)
        data = {}
        if file.exists():
            data = yaml.safe_load(file.read_text())
            if data is None:  # Catch empty file
                data = {}
        for cred in self._credentials:
            data[cred.iri] = cred.dict(exclude={"iri"})
        with open(filepath, "w") as stream:
            yaml.dump(data, stream)


CredentialManager.CredentialConfig.update_forward_refs()
