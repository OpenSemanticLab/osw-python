"""OswExpress accepts an http(s) scheme prefix and local hosts with a port."""

from unittest.mock import MagicMock

import pytest

import osw.express


@pytest.fixture
def connect(mocker):
    """Build an OswExpress with the network calls replaced by fakes.

    Returns a function that takes the domain and returns the instance, the URL
    of the reachability check and the iri passed to WtSite.
    """

    def _connect(domain):
        get = mocker.patch(
            "osw.express.requests.get", return_value=MagicMock(status_code=200)
        )
        wtsite = mocker.patch(
            "osw.express.WtSite",
            MagicMock(return_value=MagicMock(spec=osw.express.WtSite)),
        )
        instance = osw.express.OswExpress(
            domain=domain, cred_mngr=MagicMock(cred_filepath=None)
        )
        probe_url = get.call_args.args[0]
        iri = wtsite.WtSiteConfig.call_args.kwargs["iri"]
        return instance, probe_url, iri

    return _connect


@pytest.mark.parametrize(
    "given,domain,scheme,probe_url,iri",
    [
        (
            "wiki.example.org",
            "wiki.example.org",
            "https",
            "https://wiki.example.org/wiki/Main_Page",
            "wiki.example.org",
        ),
        (
            "https://wiki.example.org/",
            "wiki.example.org",
            "https",
            "https://wiki.example.org/wiki/Main_Page",
            "wiki.example.org",
        ),
        (
            "localhost:8081",
            "localhost:8081",
            "https",
            "https://localhost:8081/wiki/Main_Page",
            "localhost:8081",
        ),
        (
            "http://localhost:8081",
            "localhost:8081",
            "http",
            "http://localhost:8081/wiki/Main_Page",
            "http://localhost:8081",
        ),
        (
            "HTTP://127.0.0.1:8081",
            "127.0.0.1:8081",
            "http",
            "http://127.0.0.1:8081/wiki/Main_Page",
            "http://127.0.0.1:8081",
        ),
    ],
)
def test_scheme_prefix_and_local_hosts(connect, given, domain, scheme, probe_url, iri):
    instance, probed, site_iri = connect(given)
    assert instance.domain == domain
    assert instance.scheme == scheme
    assert probed == probe_url
    assert site_iri == iri


@pytest.mark.parametrize(
    "domain,valid",
    [
        ("wiki-dev.open-semantic-lab.org", True),
        ("sub.domain.co.uk", True),
        ("localhost", True),
        ("localhost:8081", True),
        ("127.0.0.1:8081", True),
        ("mediawiki", True),
        ("http://localhost:8081", False),
        ("not a domain!", False),
        ("-invalid.com", False),
        ("invalid-.com", False),
        ("wiki.example.org:port", False),
        ("", False),
    ],
)
def test_validate_domain(domain, valid):
    if valid:
        assert osw.express.OswExpress.validate_domain(domain) == domain
    else:
        with pytest.raises(AssertionError):
            osw.express.OswExpress.validate_domain(domain)


@pytest.mark.parametrize(
    "scheme,valid", [("http", True), ("https", True), ("ftp", False)]
)
def test_validate_scheme(scheme, valid):
    if valid:
        assert osw.express.OswExpress.validate_scheme(scheme) == scheme
    else:
        with pytest.raises(AssertionError):
            osw.express.OswExpress.validate_scheme(scheme)
