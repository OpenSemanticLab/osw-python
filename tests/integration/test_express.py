"""
This test can't be run directly (anymore) since calling fixtures directly has been
deprecated in pytest 4.0.0. Instead, the test can be run with the following command,
which requires pytest-mock to be installed:
tox -e test -- path/to/test_express.py --wiki_domain domain --wiki_username user
--wiki_password pass


Tests to be written for express.py:
* test_download_file
    * url specified
    * only title specified -> domain requested
    * target_dir (not) specified
    * target_fn (not) specified
    * target_fp (not) specified
    * osw_express (not) specified -> domain requested
    * domain (not) specified -> credentials_fp requested
    * credentials_fp (not) specified -> use fallback
    * credentials file (not) found -> check credentials_manager
    * credential_manager (not) specified -> request credentials
    * test return value
* test_upload_file
"""

from pathlib import Path

import yaml

from osw.auth import CredentialManager

# requires pytest_mock fixture --> pip install pytest-mock


def create_credentials_file(
    cred_fp: Path, wiki_domain: str, wiki_username: str, wiki_password: str
):
    with open(cred_fp, "w") as f:
        yaml.dump(
            {wiki_domain: {"username": wiki_username, "password": wiki_password}}, f
        )


def create_dummy_file(file_path: Path):
    with open(file_path, "w") as file:
        file.write("Hello, World!")


def osw_express_and_credentials(osw_express, wiki_domain, wiki_username, wiki_password):
    assert osw_express.domain == wiki_domain
    # An error would occur if the connection attempt to the wiki would have failed
    assert osw_express.site is not None
    assert osw_express.cred_fp is not None
    assert osw_express.cred_fp.exists()
    assert osw_express.cred_fp.is_file()
    credentials = yaml.safe_load(osw_express.cred_fp.open("r"))
    assert wiki_domain in credentials
    assert credentials[wiki_domain]["username"] == wiki_username
    assert credentials[wiki_domain]["password"] == wiki_password
    return True


def test_init_with_domain(wiki_domain, wiki_username, wiki_password, mocker):
    """Test OswExpress initialization with defined domain, but no cred_fp nor
    credential_manager. As this is the first test to load the osw.express module,
    the installation of the dependencies should be triggered here."""
    # Here the initial connection to the wiki is mocked (passing domain, username and
    # password)

    mocked_input = mocker.patch("builtins.input")
    mocked_getpass = mocker.patch("getpass.getpass")
    mocked_input.side_effect = [wiki_domain, wiki_username]
    mocked_getpass.return_value = wiki_password
    # This import will trigger the install_dependencies method call on the first run
    import osw.express

    # A second connection is then opened with domain already set, so mocking is
    # required for the username and password only
    mocked_input.side_effect = [wiki_username]
    mocked_getpass.return_value = wiki_password
    osw_express = osw.express.OswExpress(domain=wiki_domain)
    osw_express_and_credentials(osw_express, wiki_domain, wiki_username, wiki_password)
    assert osw_express.cred_fp == Path(osw.express.credentials_fp_default.default)
    osw_express.shut_down()
    osw_express.cred_fp.unlink()


def test_init_with_cred_fp(wiki_domain, wiki_username, wiki_password):
    """Test OswExpress initialization with defined domain and cred_fp."""
    cred_fp = Path.cwd() / "accounts.pwd.yaml"
    create_credentials_file(cred_fp, wiki_domain, wiki_username, wiki_password)
    import osw.express

    osw_express = osw.express.OswExpress(domain=wiki_domain, cred_fp=cred_fp)
    assert osw_express_and_credentials(
        osw_express, wiki_domain, wiki_username, wiki_password
    )
    assert osw_express.cred_fp == cred_fp
    osw_express.shut_down()
    cred_fp.unlink()


def test_init_with_cred_fp_but_missing_credentials(
    wiki_domain, wiki_username, wiki_password, mocker
):
    """Test OswExpress initialization with defined domain and cred_fp, but missing
    credentials."""
    mocked_input = mocker.patch("builtins.input")
    mocked_getpass = mocker.patch("getpass.getpass")
    mocked_input.return_value = wiki_username
    mocked_getpass.return_value = wiki_password
    cred_fp = Path.cwd() / "accounts.pwd.yaml"
    with open(cred_fp, "w") as f:
        yaml.dump({"dummy.domain": {"username": "dummy", "password": "password"}}, f)
    import osw.express

    osw_express = osw.express.OswExpress(domain=wiki_domain, cred_fp=cred_fp)
    assert osw_express_and_credentials(
        osw_express, wiki_domain, wiki_username, wiki_password
    )
    assert osw_express.cred_fp == cred_fp
    osw_express.shut_down()
    cred_fp.unlink()


def test_init_with_credential_manager(wiki_domain, wiki_username, wiki_password):
    """Test OswExpress initialization with defined domain and credential_manager."""
    cred_fp = Path.cwd() / "accounts.pwd.yaml"
    create_credentials_file(cred_fp, wiki_domain, wiki_username, wiki_password)
    cred_mngr = CredentialManager(cred_filepath=cred_fp)
    import osw.express

    osw_express = osw.express.OswExpress(
        domain=wiki_domain, credential_manager=cred_mngr
    )
    assert osw_express_and_credentials(
        osw_express, wiki_domain, wiki_username, wiki_password
    )
    assert osw_express.cred_fp == cred_fp
    osw_express.shut_down()
    cred_fp.unlink()


def test_file_upload_download(wiki_domain, wiki_username, wiki_password):
    cred_fp = Path.cwd() / "accounts.pwd.yaml"
    create_credentials_file(cred_fp, wiki_domain, wiki_username, wiki_password)
    import osw.express

    osw_express = osw.express.OswExpress(domain=wiki_domain, cred_fp=cred_fp)
    assert osw_express_and_credentials(
        osw_express, wiki_domain, wiki_username, wiki_password
    )
    # Test file upload
    file_path = Path.cwd() / "test_file.txt"
    create_dummy_file(file_path)
    # Upload a file to an OSW instance
    wiki_file = osw.express.osw_upload_file(file_path, osw_express=osw_express)
    local_file = osw.express.osw_download_file(wiki_file.url, osw_express=osw_express)
    assert local_file.path.exists()
    assert local_file.path.is_file()
    assert local_file.path.read_text() == "Hello, World!"
    assert local_file.url_or_title == wiki_file.url_or_title
    assert local_file.name == wiki_file.name
    # assert local_file.label[0].text == wiki_file.label[0].text  # expected behavior?
    local_file.close()
    local_file.delete()  # Delete downloaded file from local filesystem
    assert local_file.path.exists() is False
    wiki_file.delete()  # Delete WikiFile from OSW instance
    wiki_file.path.unlink()  # Delete original file from local filesystem
    assert wiki_file.path.exists() is False
    # todo: additional test required for setting / overwriting properties of the
    #  WikiFile


if __name__ == "__main__":
    cred_fp_ = Path("accounts.pwd.yaml")
    with open(cred_fp_, "r") as f:
        accounts = yaml.safe_load(f)
    wiki_domain_ = "wiki-dev.open-semantic-lab.org"
    wiki_username_ = accounts[wiki_domain_]["username"]
    wiki_password_ = accounts[wiki_domain_]["password"]
    use_pytest = False
    if use_pytest:
        # Test that require the pytest-mock fixture:
        import pytest

        # Runs all tests
        pytest.main(
            [
                __file__,
                "--wiki_domain",
                wiki_domain_,
                "--wiki_username",
                wiki_username_,
                "--wiki_password",
                wiki_password_,
            ]
        )
    else:
        # Runs tests that can be run directly:
        test_init_with_cred_fp(wiki_domain_, wiki_username_, wiki_password_)
        test_init_with_credential_manager(wiki_domain_, wiki_username_, wiki_password_)
        test_file_upload_download(wiki_domain_, wiki_username_, wiki_password_)