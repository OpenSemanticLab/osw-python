"""
Dummy conftest.py for osw.

If you don't know what this is for, just leave it empty.
Read more about conftest.py under:
- https://docs.pytest.org/en/stable/fixture.html
- https://docs.pytest.org/en/stable/writing_plugins.html
"""

import pytest

# Note: pytest_addoption lives in the repo-root conftest.py - since pytest 9.0
# it is not loaded from this subdirectory conftest via testpaths. The
# option-backed fixtures below stay here.


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
