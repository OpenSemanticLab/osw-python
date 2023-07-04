from __future__ import annotations

import getpass
from enum import Enum
from typing import List, Optional, Union

import yaml
from pydantic import FilePath

from osw.model.static import OswBaseModel


class CredentialManager(OswBaseModel):
    """Handles credentials"""

    cred_filepath: Union[Union[str, FilePath], List[Union[str, FilePath]]]
    """Filepath to yaml file with credentials for osw and connected services"""
    cert_filepath: Optional[Union[Union[str, FilePath], List[Union[str, FilePath]]]]
    """Filepath to the certificates for osw and connected services"""

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
        """internationalized resource identifier / address of the service, may contain protocol, domain, port and path
            matches by "contains" returning the shortest match"""
        fallback: Optional[CredentialManager.CredentialFallback] = "none"
        """The fallback strategy if no credential was found for the given origin"""

    def get_credential(self, config: CredentialConfig) -> BaseCredential:
        """Reads credentials from a yaml file

        Parameters
        ----------
        config:
            see CredentialConfig

        Returns
        -------
        credential :
            Credential, contain attributes 'username' and 'password' and the matching iri.
        """
        filepaths = self.cred_filepath
        if type(filepaths) is not list:
            filepaths = [filepaths]

        match_iri = ""
        cred = None
        for filepath in filepaths:
            if filepath != "":
                with open(filepath, "r") as stream:
                    try:
                        accounts = yaml.safe_load(stream)
                        for iri in accounts.keys():
                            if config.iri in iri:
                                if match_iri == "" or len(match_iri) > len(
                                    iri
                                ):  # use the less specific match
                                    match_iri = iri
                                    cred = CredentialManager.UserPwdCredential(
                                        username=accounts[iri]["username"],
                                        password=accounts[iri]["password"],
                                        iri=match_iri
                                        if len(match_iri) > len(iri)
                                        else iri  # use the more specific iri
                                        # ToDo: add support for OAuth1Credential
                                    )
                    except yaml.YAMLError as exc:
                        print(exc)
        if cred is None:
            if config.fallback is CredentialManager.CredentialFallback.ask:
                print(
                    f"No credentials for {config.iri} found. Please use the prompt to login"
                )
                username = input("Enter username")
                password = getpass.getpass("Enter password")
                cred = CredentialManager.UserPwdCredential(
                    username=username, password=password
                )
        return cred


CredentialManager.CredentialConfig.update_forward_refs()
