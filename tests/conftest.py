"""
Dummy conftest.py for osw.

If you don't know what this is for, just leave it empty.
Read more about conftest.py under:
- https://docs.pytest.org/en/stable/fixture.html
- https://docs.pytest.org/en/stable/writing_plugins.html
"""

import pytest

from osw.core import OSW
from osw.service import config
from osw.wtsite import WtPage

# Note: pytest_addoption lives in the repo-root conftest.py - since pytest 9.0
# it is not loaded from this subdirectory conftest via testpaths. The
# option-backed fixtures below stay here.


@pytest.fixture
def offline_osw(monkeypatch):
    """An OSW whose store_entity() needs no network.

    WtPage.init, the overwrite policy, WtPage.edit and the write verification
    are stubbed. A test that is about one of them replaces that stub again,
    monkeypatch applies the later call. The schema generation needs a site that
    serves the meta categories, see tests/schema_harness.py for that.
    """
    # mimic the do_init=False branch of WtPage.__init__, which sets .exists
    monkeypatch.setattr(WtPage, "init", lambda self: setattr(self, "exists", False))
    # bypass the overwrite policy: return the page that was built for the entity
    monkeypatch.setattr(
        OSW, "_apply_overwrite_policy", staticmethod(lambda param: param.page)
    )
    monkeypatch.setattr(WtPage, "edit", lambda self, *a, **kw: None)
    # the write verification would query the wiki, so report every edited page
    # as existing. See tests/test_store_entity_verify.py for its own tests.
    monkeypatch.setattr(OSW, "_get_missing_page_titles", lambda self, titles: [])
    return OSW.construct(site=object())


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
