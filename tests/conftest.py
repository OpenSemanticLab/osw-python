"""
    Dummy conftest.py for osw.

    If you don't know what this is for, just leave it empty.
    Read more about conftest.py under:
    - https://docs.pytest.org/en/stable/fixture.html
    - https://docs.pytest.org/en/stable/writing_plugins.html
"""

import pytest


def pytest_addoption(parser):
    parser.addoption("--wiki_domain", action="store")
    parser.addoption("--wiki_username", action="store")
    parser.addoption("--wiki_password", action="store")
    parser.addoption("--db_username", action="store")
    parser.addoption("--db_password", action="store")


@pytest.fixture(scope="session")
def wiki_domain(request):
    value = request.config.option.wiki_domain
    if value is None:
        pytest.skip()
    return value


@pytest.fixture(scope="session")
def wiki_username(request):
    value = request.config.option.wiki_username
    if value is None:
        pytest.skip()
    return value


@pytest.fixture(scope="session")
def wiki_password(request):
    value = request.config.option.wiki_password
    if value is None:
        pytest.skip()
    return value


@pytest.fixture(scope="session")
def db_username(request):
    value = request.config.option.db_username
    if value is None:
        pytest.skip()
    return value


@pytest.fixture(scope="session")
def db_password(request):
    value = request.config.option.db_password
    if value is None:
        pytest.skip()
    return value
