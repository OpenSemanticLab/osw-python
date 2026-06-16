"""Root conftest for pytest.

``pytest_addoption`` must live in the *rootdir* conftest (or a plugin):
since pytest 9.0 the hook is no longer picked up from a subdirectory
conftest (e.g. ``tests/conftest.py``) reached only via ``testpaths``,
which caused "unrecognized arguments: --wiki_domain ..." in CI. The
option-backed fixtures stay in ``tests/conftest.py``.
"""


def pytest_addoption(parser):
    parser.addoption("--wiki_domain", action="store")
    parser.addoption("--wiki_username", action="store")
    parser.addoption("--wiki_password", action="store")
    parser.addoption("--db_username", action="store")
    parser.addoption("--db_password", action="store")
