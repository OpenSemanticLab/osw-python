"""
Dummy conftest.py for osw.

If you don't know what this is for, just leave it empty.
Read more about conftest.py under:
- https://docs.pytest.org/en/stable/fixture.html
- https://docs.pytest.org/en/stable/writing_plugins.html
"""

import pytest

from osw.service import config

# Note: pytest_addoption lives in the repo-root conftest.py - since pytest 9.0
# it is not loaded from this subdirectory conftest via testpaths. The
# option-backed fixtures below stay here.


@pytest.fixture(autouse=True)
def _restore_log_prefix():
    """Restore ``osw.service.config._LOG_PREFIX`` after each test.

    It is process-wide mutable state, set once by whichever adapter starts a
    process (see ``config.set_log_prefix``). Without this, a test that sets
    it directly, or indirectly by exercising the CLI or the MCP server, would
    leak that choice into a later test that expects the default.
    """
    original = config._LOG_PREFIX
    yield
    config._LOG_PREFIX = original


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
