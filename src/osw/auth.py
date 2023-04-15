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
    """yaml file with credentials for osw and connected services"""

    class Credential(OswBaseModel):
        """_summary_

        Parameters
        ----------
        username:
            the user identifier
        password:
            the users password
        """

        username: str
        password: str

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
        """Reads credentials from a yaml file

        Parameters
        ----------
        iri:
            internationalized resource identifier / address of the service, may contain protocol, domain, port and path
            matches by "contains" returning the shortest match
        fallback:
            The fallback strategy if no credential was found for the given origin
        """

        iri: str
        fallback: Optional[CredentialManager.CredentialFallback] = "none"

    def get_credential(self, config: CredentialConfig) -> Credential:
        """Reads credentials from a yaml file

        Parameters
        ----------
        config:
            see CredentialConfig

        Returns
        -------
        credential :
            Credential, contain attributes 'username' and 'password'.
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
                                if match_iri == "" or len(match_iri) > len(iri):
                                    match_iri = iri
                                    cred = CredentialManager.Credential(
                                        username=accounts[iri]["username"],
                                        password=accounts[iri]["password"],
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
                cred = CredentialManager.Credential(
                    username=username, password=password
                )
        return cred


CredentialManager.CredentialConfig.update_forward_refs()
