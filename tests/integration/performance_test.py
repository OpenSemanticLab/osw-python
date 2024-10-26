import time

import pytest

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.wtsite import WtSite


def test_fetch_and_load(wiki_domain, wiki_username, wiki_password, mocker):
    # create a credential file on the default path for osw express
    cm = CredentialManager()  # cred_filepath = Path.cwd() / "accounts.pwd.yaml")
    cm.add_credential(
        CredentialManager.UserPwdCredential(
            iri=wiki_domain, username=wiki_username, password=wiki_password
        )
    )
    # cm.save_credentials_to_file()
    # wtsite = WtSite(WtSite.WtSiteConfig(iri=wiki_domain, cred_mngr=cm))
    # osw_obj = OSW(site=wtsite)

    # Here the initial connection to the wiki is mocked (passing domain, username and
    # password)
    if mocker is not None:
        mocked_input = mocker.patch("builtins.input")
        mocked_getpass = mocker.patch("getpass.getpass")
        mocked_input.side_effect = [wiki_domain, wiki_username]
        mocked_getpass.return_value = wiki_password
    # This import will trigger the install_dependencies method call on the first run
    import osw.express

    osw_express = osw.express.OswExpress(domain=wiki_domain, cred_mngr=cm)

    # Measure the time taken to store and load an entity
    start_time = time.time()

    # Load Tutorial Schema on demand
    # if not hasattr(model, "Tutorial"):
    DEPENDENCIES = {"Tutorial": "Category:OSW494f660e6a714a1a9681c517bbb975da"}
    osw_express.install_dependencies(DEPENDENCIES, policy="force")

    end_time = time.time()
    print(f"Time taken to load Tutorial Schema: {end_time - start_time}")
    assert hasattr(model, "Tutorial")
    assert end_time - start_time < 32  # typically takes 8 seconds

    start_time = time.time()
    osw_express.install_dependencies(DEPENDENCIES, policy="force")
    end_time = time.time()
    print(
        f"Time taken to reload Tutorial Schema with policy 'force': {end_time - start_time}"
    )
    assert end_time - start_time < 4  # typically takes 1 seconds using memory cache

    start_time = time.time()
    osw_express.install_dependencies(DEPENDENCIES, policy="if-missing")
    end_time = time.time()
    print(
        "Time taken to reload Tutorial Schema with policy ",
        f"'if-missing': {end_time - start_time}",
    )
    assert end_time - start_time < 0.5  # typically takes 0 seconds

    # query any 50 Category pages
    pages = osw_express.query_instances("Category:Category")
    start_time = time.time()
    result = osw_express.site.get_page(WtSite.GetPageParam(titles=pages[:50]))
    end_time = time.time()
    print(f"Time taken to fetch 50 Category pages: {end_time - start_time}")
    assert (
        end_time - start_time < 15
    )  # typically takes 3.5 (dask) or 2.7 (asyncio) seconds

    assert len(result.pages) == 50

    # we should get a warning for the non-existent page
    # see https://docs.pytest.org/en/stable/how-to/capture-warnings.html
    pages[0] = "IDONOTEXIST"
    with pytest.warns(RuntimeWarning) as record:
        result = osw_express.site.get_page(
            WtSite.GetPageParam(titles=pages[:50], raise_exception=False)
        )
        # assert that at least one warning message contains
        # the missing page title to inform the user
        assert any("IDONOTEXIST" in str(rec.message) for rec in record)
        assert len(result.pages) == 50  # assert that the result is still returned

    # assert that ValueError is raised when the page does not exist
    pages[0] = "IDONOTEXIST"
    with pytest.raises(ValueError):
        result = osw_express.site.get_page(
            WtSite.GetPageParam(titles=pages[:50], raise_exception=True)
        )
