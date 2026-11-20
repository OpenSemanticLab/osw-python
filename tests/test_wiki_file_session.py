"""Unit tests for how a wiki file controller finds its session.

The session is optional: a controller built from a file entity connects on
first use. A file that is about to be uploaded has no URL yet - that is what
the upload produces - so the URL cannot be the only way to find the wiki.

Offline: the session is never built here, only the inputs that decide which
one would be.
"""

from io import BytesIO

import pytest
from oold.backend.auth import UserPwdCredential, set_credential

import osw.controller.file.wiki as wiki_module
from osw.controller.file.local import LocalFileController
from osw.controller.file.wiki import OSW, WikiFileController, WtSite


@pytest.fixture(autouse=True)
def _clean_credentials(monkeypatch):
    """Keep the process-wide credential store and session cache per test."""
    import oold.backend.auth as auth

    saved = auth._credentials.get()
    auth._credentials.set({})
    wiki_module.clear_sessions()
    yield
    auth._credentials.set(saved)
    wiki_module.clear_sessions()


def _credential(iri, username="bot", password="secret"):
    return UserPwdCredential(iri=iri, username=username, password=password)


def _a_session() -> OSW:
    """A stand-in session: only which one travels is under test.

    pydantic v1 copies a model on assignment, so the controller does not hold
    the very object that was passed in; the sessions are told apart by the
    site they carry.
    """
    return OSW.construct(site=WtSite.__new__(WtSite))


def _controller(**kwargs):
    return WikiFileController(**kwargs)


# -- choosing the wiki --------------------------------------------------------


def test_a_url_decides_the_wiki():
    controller = _controller(download_url="https://wiki.example.org/wiki/File:A.bin")
    assert controller._session_url() == "https://wiki.example.org/wiki/File:A.bin"


def test_without_a_url_the_single_registered_credential_decides():
    """A fresh upload has no URL, so the credential is the only pointer."""
    set_credential(_credential("wiki.example.org"))
    assert _controller()._session_url() == "wiki.example.org"


def test_without_a_url_and_without_a_credential_the_error_says_so():
    with pytest.raises(ValueError, match="no credential is registered"):
        _controller()._session_url()


def test_several_credentials_without_a_url_are_ambiguous():
    set_credential(_credential("wiki.example.org"))
    set_credential(_credential("other.example.org"))
    with pytest.raises(ValueError, match=r"other\.example\.org"):
        _controller()._session_url()


def test_a_session_that_was_passed_in_is_kept():
    sentinel = _a_session()
    controller = _controller(osw=sentinel)
    assert controller._ensure_session().site is sentinel.site


# -- the session cache --------------------------------------------------------


@pytest.fixture
def built_sites(monkeypatch):
    """Record the WtSite configs built, instead of connecting to a wiki."""
    configs = []

    def _config(**kwargs):
        configs.append(kwargs)
        return kwargs

    monkeypatch.setattr(
        wiki_module, "OSW", lambda site: f"session{len(configs)}:{site['iri']}"
    )
    monkeypatch.setattr(wiki_module, "WtSite", lambda config: config)
    monkeypatch.setattr(wiki_module.WtSite, "WtSiteConfig", _config, raising=False)
    return configs


def test_sessions_are_cached_per_credential(built_sites):
    """Two path-scoped credentials of one host are two logins."""
    set_credential(_credential("wiki.example.org/a", username="a"))
    set_credential(_credential("wiki.example.org/b", username="b"))

    first = wiki_module.session_for("https://wiki.example.org/a/File:X")
    second = wiki_module.session_for("https://wiki.example.org/b/File:X")
    again = wiki_module.session_for("https://wiki.example.org/a/File:Y")

    assert first != second
    assert again == first
    # and every one of them talks to the host, not to host/path
    assert {config["iri"] for config in built_sites} == {"wiki.example.org"}


def test_one_credential_does_not_collapse_two_hosts(built_sites):
    """oold matches a stored IRI inside the searched one, so one credential
    answers for every subdomain - that must not share a session."""
    set_credential(_credential("example.org"))

    first = wiki_module.session_for("https://wiki-a.example.org/wiki/File:X")
    second = wiki_module.session_for("https://wiki-b.example.org/wiki/File:Y")

    assert first != second
    assert [config["iri"] for config in built_sites] == [
        "wiki-a.example.org",
        "wiki-b.example.org",
    ]


def test_a_bare_credential_iri_still_names_the_host(built_sites):
    """The no-URL path hands the credential key straight to session_for."""
    set_credential(_credential("wiki.example.org/w"))

    wiki_module.session_for(_controller()._session_url())

    assert built_sites[0]["iri"] == "wiki.example.org"


def test_a_replaced_credential_replaces_the_session(built_sites):
    """A later set_credential must not be ignored for the process lifetime."""
    set_credential(_credential("wiki.example.org", password="old"))
    first = wiki_module.session_for("https://wiki.example.org/File:X")

    set_credential(_credential("wiki.example.org", password="new"))
    second = wiki_module.session_for("https://wiki.example.org/File:X")

    assert second != first
    assert len(built_sites) == 2


def test_a_missing_credential_is_reported_with_the_host():
    with pytest.raises(ValueError, match=r"wiki\.example\.org"):
        wiki_module.session_for("https://wiki.example.org/File:X")


# -- from_other ---------------------------------------------------------------


def test_from_other_keeps_a_session_the_source_carries():
    sentinel = _a_session()
    source = WikiFileController(osw=sentinel, download_url="https://w.example/x")

    target = WikiFileController.from_other(source)

    assert target.osw.site is sentinel.site


def test_from_other_takes_the_session_it_is_given():
    sentinel = _a_session()
    other = _a_session()
    source = WikiFileController(osw=other, download_url="https://w.example/x")

    target = WikiFileController.from_other(source, osw=sentinel)

    assert target.osw.site is sentinel.site
    assert target.osw.site is not other.site


# -- the local controller -----------------------------------------------------


def test_local_controller_needs_a_file():
    with pytest.raises(ValueError, match="needs a file"):
        LocalFileController()


def test_local_controller_accepts_path_or_local_path(tmp_path):
    target = tmp_path / "a.bin"
    target.write_bytes(b"x")

    assert LocalFileController(path=target).path == target
    assert LocalFileController(local_path=str(target)).path == target


def test_local_controller_round_trips_a_file(tmp_path):
    controller = LocalFileController(path=tmp_path / "a.bin")
    controller.put(BytesIO(b"payload"))
    with controller.get() as handle:
        assert handle.read() == b"payload"
