from __future__ import annotations

import getpass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union
from warnings import warn

import yaml
from pydantic.v1 import FilePath, PrivateAttr

from osw.model.static import OswBaseModel

CREDENTIALS_FN_DEFAULT = "credentials.pwd.yaml"


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
        # Make sure to at least warn the user if they pass cred_fp instead of
        # cred_filepath
        attribute_names = self.__dict__.keys()
        unexpected_kwargs = [key for key in data.keys() if key not in attribute_names]
        if unexpected_kwargs:
            warn(f"Unexpected keyword argument(s): {', '.join(unexpected_kwargs)}")

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
                    with open(filepath, "r", encoding="utf-8") as stream:
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
                self.add_credential(cred)
                if self.cred_filepath:
                    self.save_credentials_to_file()
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
            for fp in self.cred_filepath:
                if fp != "":
                    if Path(fp).exists():
                        with open(fp, "r", encoding="utf-8") as stream:
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
        filepath_ = [filepath]
        if filepath is None:
            filepath_ = self.cred_filepath
            if self.cred_filepath is None:
                filepath_ = [Path.cwd() / CREDENTIALS_FN_DEFAULT]
        if set_cred_filepath:
            self.cred_filepath = filepath_
        for fp in filepath_:
            file = Path(fp)
            if not file.parent.exists():
                file.parent.mkdir(parents=True)
            data = {}
            file_already_exists = file.exists()
            if file_already_exists:
                data = yaml.safe_load(file.read_text(encoding="utf-8"))
                if data is None:  # Catch empty file
                    data = {}
            for cred in self._credentials:
                data[cred.iri] = cred.dict(exclude={"iri"})
            with open(fp, "w", encoding="utf-8") as stream:
                yaml.dump(data, stream)
            if file_already_exists:
                print(f"Credentials file updated at '{fp.resolve()}'.")
            else:
                print(f"Credentials file created at '{fp.resolve()}'.")

        # Creating or updating .gitignore file in the working directory
        cwd = Path.cwd()
        potential_fp = [cwd / ".gitignore", cwd.parent / ".gitignore"]
        write_to_fp = potential_fp[0]
        for fp in potential_fp:
            if fp.exists():
                write_to_fp = fp
                break
        if not write_to_fp.exists():
            if not write_to_fp.parent.exists():
                write_to_fp.parent.mkdir(parents=True)
            write_to_fp.touch()
        with open(write_to_fp, "r") as stream:
            content = stream.read()
        comment_set = False
        for _ii, fp in enumerate(filepath_):
            if fp.name not in content:
                print(f"Adding '{fp.name}' to gitignore file '{write_to_fp}'.")
                with open(write_to_fp, "a") as stream:
                    if comment_set:
                        stream.write(
                            "\n# Automatically added by osw.auth.CredentialManager."
                            "save_credentials_to_file:"
                        )
                        comment_set = True
                    stream.write(f"\n*{fp.name}")


CredentialManager.CredentialConfig.update_forward_refs()
