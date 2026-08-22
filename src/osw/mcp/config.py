"""Configuration for the osw-mcp server.

Loads settings from the environment (optionally via a ``.env`` file) and
validates that connection credentials are present *before* the server ever
touches the osw library. This matters because ``OswExpress`` / ``SmwSparqlClient``
fall back to an interactive ``input()`` / ``getpass`` prompt when credentials are
missing, which would hang a stdio MCP server (it would read the JSON-RPC stream
as a password). We therefore fail fast with a clear error instead.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yaml

# python-dotenv is part of the [mcp] extra
from dotenv import load_dotenv

from osw.auth import CredentialManager

_TRUTHY = {"1", "true", "yes", "on"}

# Environment variable names (OSL_* are accepted as fallbacks, matching osw).
ENV_DOMAIN = ("OSW_DOMAIN", "OSL_DOMAIN")
ENV_USERNAME = ("OSW_USERNAME", "OSL_USERNAME")
ENV_PASSWORD = ("OSW_PASSWORD", "OSL_PASSWORD")
# OSL_CRED_FILEPATH is accepted because existing osw deployments already set it.
ENV_CRED_FILEPATH = ("OSW_MCP_CRED_FILEPATH", "OSL_CRED_FILEPATH")


def _first_env(names: tuple[str, ...]) -> Optional[str]:
    """Return the first non-empty environment value among ``names``."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


@dataclass(frozen=True)
class Settings:
    """Resolved, validated server settings."""

    # domain is optional: with a usable credential file, no domain need be
    # configured via the environment; the active instance is then chosen from
    # the credential file (auto-selected or via the select_instance tool).
    domain: Optional[str]
    # username/password are optional: a configured credential file is an
    # alternative source of credentials (see ENV_CRED_FILEPATH).
    username: Optional[str] = None
    # kept only to build the SPARQL client; never returned by any tool
    password: Optional[str] = field(default=None, repr=False)
    cred_filepath: Optional[str] = None
    sparql_endpoint: Optional[str] = None
    read_only: bool = False
    state_dir: Optional[str] = None
    max_results: int = 100
    max_chars: int = 100_000

    def redacted(self) -> dict:
        """A dict view safe for logging / the status tool (no password)."""
        return {
            "domain": self.domain,
            "username": self.username,
            "read_only": self.read_only,
            "sparql_endpoint_configured": bool(self.sparql_endpoint),
            "cred_filepath_configured": bool(self.cred_filepath),
        }


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(
            f"Environment variable {name}={raw!r} is not a valid integer."
        )


def _cred_file_iris(cred_filepath: str) -> list[str]:
    """Return the top-level iri keys in a credential YAML file, best effort."""
    try:
        with open(cred_filepath, encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError):
        return []
    if not data:
        return []
    return sorted(str(key) for key in data.keys())


def _derive_domain(iri: str) -> str:
    """Derive a bare domain from ``iri`` (a bare domain or a full URL).

    ``OswExpress`` requires a bare domain and validates it with a regex, but
    credential-file iris may be either a bare domain (``wiki.example.org``) or
    a full URL (``https://wiki.example.org/w/``).
    """
    if "://" in iri:
        netloc = urlparse(iri).netloc
    else:
        netloc = iri.split("/", 1)[0]
    return netloc.rstrip(".")


def _verify_cred_file_has_domain(cred_filepath: str, domain: str) -> None:
    """Verify that the credential file has an entry matching ``domain``.

    Uses ``CredentialManager.get_credential`` with ``fallback="none"`` so this
    never prompts interactively and never performs a network login; it only
    checks that a matching credential entry already exists in the file.

    Raises
    ------
    RuntimeError
        If no credential entry matches ``domain``, naming the iris the file
        does contain (never their secrets) so the operator can fix it.
    """
    cred_mngr = CredentialManager(cred_filepath=cred_filepath)
    credential = cred_mngr.get_credential(
        CredentialManager.CredentialConfig(
            iri=domain, fallback=CredentialManager.CredentialFallback.none
        )
    )
    if credential is None:
        available = ", ".join(_cred_file_iris(cred_filepath)) or "(none)"
        raise RuntimeError(
            f"Credential file '{cred_filepath}' has no entry matching domain "
            f"'{domain}'. Iris found in the file: {available}. Add an entry "
            "for the domain, or configure OSW_USERNAME/OSW_PASSWORD instead."
        )


def load() -> Settings:
    """Load and validate settings from the environment.

    Loads a ``.env`` file first: the path in ``OSW_MCP_ENV_FILE`` if set,
    otherwise dotenv's default search from the current working directory upward.

    Credentials can come from either ``OSW_USERNAME``/``OSW_PASSWORD`` (or
    their ``OSL_*`` aliases) or from a credential file configured via
    ``OSW_MCP_CRED_FILEPATH`` / ``OSL_CRED_FILEPATH``. When a credential file
    is configured, it is validated here to actually contain an entry for the
    configured domain.

    Raises
    ------
    RuntimeError
        If domain is missing and no usable credential file is configured, if
        neither a usable credential file nor username/password are
        configured, if a configured credential file does not exist, or if a
        configured credential file has no entry matching a configured domain.
        This keeps the osw interactive credential prompt from ever being
        reached.
    """
    env_file = os.getenv("OSW_MCP_ENV_FILE")
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    domain = _first_env(ENV_DOMAIN)
    username = _first_env(ENV_USERNAME)
    password = _first_env(ENV_PASSWORD)
    cred_filepath = _first_env(ENV_CRED_FILEPATH)

    cred_file_usable = False
    if cred_filepath:
        if not Path(cred_filepath).is_file():
            raise RuntimeError(
                f"Configured credential file '{cred_filepath}' does not exist. "
                "Set OSW_MCP_CRED_FILEPATH / OSL_CRED_FILEPATH to a valid path, "
                "or remove it and configure OSW_USERNAME/OSW_PASSWORD instead."
            )
        cred_file_usable = True

    # A usable credential file makes the domain optional: which instance to
    # use is then chosen later (auto-selected or via select_instance).
    checks = []
    if not cred_file_usable:
        checks.append((ENV_DOMAIN, domain))
        checks.append((ENV_USERNAME, username))
        checks.append((ENV_PASSWORD, password))
    missing = [names[0] for names, value in checks if not value]
    if missing:
        raise RuntimeError(
            "Missing required OSW credential environment variables: "
            + ", ".join(missing)
            + ". Set them in your environment or a .env file "
            "(pointed to by OSW_MCP_ENV_FILE), or configure a credential file "
            "via OSW_MCP_CRED_FILEPATH / OSL_CRED_FILEPATH. The server refuses "
            "to start without them to avoid an interactive credential prompt "
            "that would hang the stdio transport."
        )

    if cred_file_usable and domain:
        _verify_cred_file_has_domain(cred_filepath, domain)

    return Settings(
        domain=domain,
        username=username,
        password=password,
        cred_filepath=cred_filepath,
        sparql_endpoint=os.getenv("OSW_SPARQL_ENDPOINT") or None,
        read_only=(os.getenv("OSW_MCP_READ_ONLY", "").lower() in _TRUTHY),
        state_dir=os.getenv("OSW_MCP_STATE_DIR") or None,
        max_results=_int_env("OSW_MCP_MAX_RESULTS", 100),
        max_chars=_int_env("OSW_MCP_MAX_CHARS", 100_000),
    )


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Return cached settings, loading (and validating) them on first use."""
    global _settings
    if _settings is None:
        _settings = load()
    return _settings


def reset() -> None:
    """Drop cached settings and the active-instance selection (used by tests)."""
    global _settings, _active_iri, _active_resolved
    _settings = None
    _active_iri = None
    _active_resolved = False


# -- active-instance state ---------------------------------------------------
#
# A server can be configured with several candidate instances (an
# env-configured domain and/or the iris in a credential file). Exactly one of
# them is "active" at a time; tools connect to whichever one is active. The
# active instance is auto-selected on first access (see ``_auto_select_iri``)
# and can be changed at runtime via ``set_active_instance`` (the
# ``select_instance`` tool).

_active_iri: Optional[str] = None
_active_resolved: bool = False


def _auto_select_iri() -> Optional[str]:
    """Auto-select the active iri, or return ``None`` if none can be chosen.

    1. A domain configured via the environment is always the active instance.
    2. Otherwise, if a credential file is configured and contains exactly one
       iri, that iri is the active instance.
    3. Otherwise there is no active instance until ``set_active_instance`` is
       called (e.g. via the ``select_instance`` tool).
    """
    settings = get_settings()
    if settings.domain:
        return settings.domain
    if settings.cred_filepath:
        iris = _cred_file_iris(settings.cred_filepath)
        if len(iris) == 1:
            return iris[0]
    return None


def available_iris() -> list[str]:
    """Return every iri this server can connect to.

    Combines the env-configured domain (if any) with the iris found in a
    configured credential file (if any), without duplicates. Never includes
    usernames, passwords, or any other credential value.
    """
    settings = get_settings()
    iris: list[str] = []
    if settings.domain:
        iris.append(settings.domain)
    if settings.cred_filepath:
        for iri in _cred_file_iris(settings.cred_filepath):
            if iri not in iris:
                iris.append(iri)
    return iris


def get_active_iri() -> Optional[str]:
    """Return the active instance iri, auto-selecting it on first access."""
    global _active_iri, _active_resolved
    if not _active_resolved:
        _active_iri = _auto_select_iri()
        _active_resolved = True
    return _active_iri


def get_active_domain() -> Optional[str]:
    """Return the bare domain of the active instance, or ``None`` if unset."""
    iri = get_active_iri()
    if iri is None:
        return None
    return _derive_domain(iri)


def set_active_instance(iri: str) -> None:
    """Set the active instance to ``iri``.

    Raises
    ------
    ValueError
        If ``iri`` is not one of :func:`available_iris`, naming the iris that
        are available so the caller can pick a valid one.
    """
    global _active_iri, _active_resolved
    available = available_iris()
    if iri not in available:
        raise ValueError(
            f"Unknown instance '{iri}'. Available: "
            + (", ".join(available) or "(none)")
        )
    _active_iri = iri
    _active_resolved = True


def get_active_credentials() -> tuple[Optional[str], Optional[str]]:
    """Return the username/password to use for the currently active instance.

    Resolution order:

    1. If a credential file is configured, look up the active iri via
       ``CredentialManager.get_credential`` with ``fallback=CredentialFallback.none``
       (never prompts interactively, never performs a network login). A
       ``UserPwdCredential`` match yields its username/password. A match of any
       other credential kind (e.g. ``OAuth1Credential``, which has no
       username/password) yields ``(None, None)``.
    2. Otherwise (no credential file configured, or no match found in it),
       fall back to ``settings.username`` / ``settings.password``.
    3. If neither source yields anything, returns ``(None, None)``.

    Never raises and never prompts, so this is always safe to call from a
    stdio MCP tool.
    """
    settings = get_settings()
    active_iri = get_active_iri()
    if settings.cred_filepath and active_iri:
        cred_mngr = CredentialManager(cred_filepath=settings.cred_filepath)
        credential = cred_mngr.get_credential(
            CredentialManager.CredentialConfig(
                iri=active_iri, fallback=CredentialManager.CredentialFallback.none
            )
        )
        if credential is not None:
            if isinstance(credential, CredentialManager.UserPwdCredential):
                return credential.username, credential.password
            return None, None
    return settings.username, settings.password
