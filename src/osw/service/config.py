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
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from osw.auth import CredentialManager

# Environment variable names. Each tuple lists the canonical ``OSW_*`` name
# first, followed by every alias that must keep working. ``OSW_CRED_FILEPATH``
# is canonical (rather than an ``OSW_MCP_``-prefixed name) because
# ``osw.express`` already reads that exact name (see ``src/osw/express.py``,
# search for ``CRED_FILEPATH``); the ``OSW_MCP_`` prefix used elsewhere was a
# gratuitous divergence from that. ``OSL_*`` names are accepted as legacy
# fallbacks, matching osw itself.
ENV_DOMAIN = ("OSW_DOMAIN", "OSL_DOMAIN")
ENV_USERNAME = ("OSW_USERNAME", "OSL_USERNAME")
ENV_PASSWORD = ("OSW_PASSWORD", "OSL_PASSWORD")
ENV_CRED_FILEPATH = ("OSW_CRED_FILEPATH", "OSW_MCP_CRED_FILEPATH", "OSL_CRED_FILEPATH")
ENV_SPARQL_ENDPOINT = ("OSW_SPARQL_ENDPOINT",)
ENV_READ_ONLY = ("OSW_READ_ONLY", "OSW_MCP_READ_ONLY")
ENV_STATE_DIR = ("OSW_STATE_DIR", "OSW_MCP_STATE_DIR")
ENV_MAX_RESULTS = ("OSW_MAX_RESULTS", "OSW_MCP_MAX_RESULTS")
ENV_MAX_CHARS = ("OSW_MAX_CHARS", "OSW_MCP_MAX_CHARS")
ENV_FILE = ("OSW_ENV_FILE", "OSW_MCP_ENV_FILE")


def _first_env(names: tuple[str, ...]) -> Optional[str]:
    """Return the first non-empty environment value among ``names``."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


# Which env variable tuple feeds each Settings field, used to name the offending
# variable when pydantic rejects a value.
_ENV_BY_FIELD: dict[str, tuple[str, ...]] = {
    "domain": ENV_DOMAIN,
    "username": ENV_USERNAME,
    "password": ENV_PASSWORD,
    "cred_filepath": ENV_CRED_FILEPATH,
    "sparql_endpoint": ENV_SPARQL_ENDPOINT,
    "read_only": ENV_READ_ONLY,
    "state_dir": ENV_STATE_DIR,
    "max_results": ENV_MAX_RESULTS,
    "max_chars": ENV_MAX_CHARS,
}


def _env_name_for(field_name: str) -> str:
    """Name the env variable that actually supplied ``field_name``.

    Falls back to the canonical name so the operator always gets something
    actionable to fix.
    """
    names = _ENV_BY_FIELD.get(field_name, ())
    if not names:
        return field_name
    for name in names:
        if os.getenv(name):
            return name
    return names[0]


class Settings(BaseModel):
    """Resolved, validated server settings."""

    model_config = ConfigDict(frozen=True)

    # domain is optional: with a usable credential file, no domain need be
    # configured via the environment; the active instance is then chosen from
    # the credential file (auto-selected, or picked with the CLI's --instance).
    domain: Optional[str]
    # username/password are optional: a configured credential file is an
    # alternative source of credentials (see ENV_CRED_FILEPATH).
    username: Optional[str] = None
    # kept only to build the SPARQL client; never returned by any tool
    password: Optional[str] = Field(default=None, repr=False)
    cred_filepath: Optional[str] = None
    sparql_endpoint: Optional[str] = None
    read_only: bool = False
    state_dir: Optional[str] = None
    max_results: int = Field(default=100, gt=0)
    max_chars: int = Field(default=100_000, gt=0)

    @field_validator("domain")
    @classmethod
    def _validate_domain(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("must not be empty or whitespace-only")
        if any(char.isspace() for char in value):
            raise ValueError("must not contain whitespace")
        if any(ord(char) < 32 for char in value):
            raise ValueError("must not contain control characters")
        return value

    @field_validator("sparql_endpoint")
    @classmethod
    def _validate_sparql_endpoint(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(
                "must be a valid http(s) URL (e.g. 'https://wiki.example.org/sparql')"
            )
        return value

    @field_validator("state_dir")
    @classmethod
    def _validate_state_dir(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("must not be empty or whitespace-only")
        return value

    @field_validator("cred_filepath")
    @classmethod
    def _validate_cred_filepath(cls, value: Optional[str]) -> Optional[str]:
        # Control characters are deliberately not rejected here: load() already
        # produces a much better, hint-carrying error for that case via
        # _escape_hint(), and that check runs before Settings is constructed.
        if value is None:
            return value
        if not value.strip():
            raise ValueError("must not be empty or whitespace-only")
        return value

    def redacted(self) -> dict:
        """A dict view safe for logging / the status tool (no password)."""
        return {
            "domain": self.domain,
            "username": self.username,
            "read_only": self.read_only,
            "sparql_endpoint_configured": bool(self.sparql_endpoint),
            "cred_filepath_configured": bool(self.cred_filepath),
        }


def _escape_hint(value: str) -> str:
    """Extra error text when ``value`` holds a control character, else "".

    A double-quoted value in a ``.env`` file goes through escape decoding, so
    a Windows path like ``"C:\\dir\\accounts.yaml"`` silently loses its ``\\a``
    to a BEL byte. The result renders as nothing in a terminal, which makes the
    resulting "does not exist" message look like it is naming the right path.
    """
    if not any(ord(char) < 32 for char in value):
        return ""
    return (
        f" The configured path contains a control character ({value!r}). A "
        "double-quoted value in a .env file is escape-decoded, so a Windows "
        r"path loses sequences like \a, \b, \f, \n, \r, \t and \v. Use single "
        "quotes, no quotes, forward slashes, or doubled backslashes."
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


# Whether to look for a .env file when none is configured explicitly. Off by
# default, so a process only reads a file it was pointed at: the MCP server's
# working directory is chosen by the MCP client, so searching it would make
# which credentials get loaded depend on how the client was launched. The CLI
# turns it on (see osw.cli.main), where the working directory is the one the
# user typed the command in.
_discover_env_file: bool = False

# Where the .env file actually came from, for the startup banner. One of
# "explicit", "discovered", "none" (searched, nothing found) or "not searched".
_env_file_path: Optional[str] = None
_env_file_origin: str = "not searched"


def set_env_file_discovery(enabled: bool) -> None:
    """Enable or disable the implicit ``.env`` search (default: disabled).

    Must be called before settings are first loaded, since the file is read
    exactly once per process; a call that would *change* the setting after
    that raises rather than silently having no effect. Re-asserting the
    current value is always allowed, so an adapter can call this on every
    command without tracking whether it already did.
    """
    global _discover_env_file
    if enabled != _discover_env_file and _settings is not None:
        raise RuntimeError(
            "set_env_file_discovery() must be called before settings are "
            "loaded; they are already cached for this process."
        )
    _discover_env_file = enabled


def _load_env_file() -> None:
    """Load a .env file if one is configured or (when enabled) discoverable.

    dotenv is a base dependency, so it is normally present. It is still
    imported defensively, for an environment that stripped it: an *explicitly*
    configured env file with dotenv missing is an error, because the operator
    asked for something that cannot happen. An implicit search is skipped
    silently.

    The implicit search starts at the current working directory and walks
    upward. ``dotenv.load_dotenv()`` with no arguments would instead walk up
    from the *calling module's* directory, which is this file: under an
    editable install that is the osw checkout and under a normal install it is
    site-packages. Neither is what a user standing in a project directory
    means by "the .env file", hence the explicit ``usecwd=True``.
    """
    global _env_file_path, _env_file_origin
    path = _first_env(ENV_FILE)
    try:
        import dotenv
    except ImportError:
        if path is None:
            return
        name = next((n for n in ENV_FILE if os.getenv(n) == path), ENV_FILE[0])
        raise RuntimeError(
            f"{name} is set (to '{path}') but python-dotenv is not installed. "
            "Install python-dotenv (a dependency of osw) to use an env file."
        )
    if path:
        dotenv.load_dotenv(path)
        _env_file_path, _env_file_origin = path, "explicit"
        return
    if not _discover_env_file:
        return
    found = dotenv.find_dotenv(usecwd=True)
    if not found:
        _env_file_origin = "none"
        return
    dotenv.load_dotenv(found)
    _env_file_path, _env_file_origin = found, "discovered"


def log_config_sources(stream=None) -> None:
    """Print where configuration was read from, one line per source.

    Loads the ``.env`` file first if that has not happened yet, and reads the
    environment directly rather than a ``Settings``. Both so this can run
    *before* settings are loaded: a misconfiguration makes loading raise, and
    that is exactly when knowing which files were read matters most.

    Always writes to ``stderr``: under MCP ``stdout`` carries the JSON-RPC
    stream, and under ``osw --json`` it carries the result payload.
    """
    _load_env_file()
    out = sys.stderr if stream is None else stream
    described = {
        "explicit": f"{_env_file_path} (from {ENV_FILE[0]})",
        "discovered": f"{_env_file_path} (found from the working directory upward)",
        "none": "none found (searched from the working directory upward)",
        "not searched": f"not configured (set {ENV_FILE[0]} to use one)",
    }[_env_file_origin]
    print(f"[osw] env file       : {described}", file=out)
    cred_filepath = _first_env(ENV_CRED_FILEPATH)
    if cred_filepath:
        print(f"[osw] credential file: {cred_filepath}", file=out)


def load(strict: bool = True) -> Settings:
    """Load and validate settings from the environment.

    Loads a ``.env`` file first: the path in ``OSW_ENV_FILE`` (or its
    ``OSW_MCP_ENV_FILE`` alias) if set, otherwise a search from the current
    working directory upward, but only when ``set_env_file_discovery(True)``
    has enabled it (the CLI does; the MCP server does not).

    Credentials can come from either ``OSW_USERNAME``/``OSW_PASSWORD`` (or
    their ``OSL_*`` aliases) or from a credential file configured via
    ``OSW_CRED_FILEPATH`` (or its ``OSW_MCP_CRED_FILEPATH`` / ``OSL_CRED_FILEPATH``
    aliases). When a credential file is configured, it is validated here to
    actually contain an entry for the configured domain.

    Parameters
    ----------
    strict:
        When ``True`` (the default), missing required credentials (no domain
        + username/password and no usable credential file) raise
        ``RuntimeError``. When ``False``, that specific check is skipped and a
        best-effort ``Settings`` is returned instead, with whatever was found
        (fields may be ``None``) -- useful for a status command that wants to
        report "not configured" rather than crash. Every other error still
        raises regardless of ``strict``: a configured credential file that
        does not exist, a configured credential file with no entry matching a
        configured domain, an environment variable holding a value the
        settings model rejects (an unparseable or non-positive integer, a
        malformed SPARQL endpoint URL, a domain containing whitespace), and a
        missing ``python-dotenv`` for an explicitly configured env file.

    Raises
    ------
    RuntimeError
        If domain is missing and no usable credential file is configured, if
        neither a usable credential file nor username/password are
        configured (only when ``strict`` is ``True``), if a configured
        credential file does not exist, or if a configured credential file has
        no entry matching a configured domain. This keeps the osw interactive
        credential prompt from ever being reached.
    """
    _load_env_file()

    domain = _first_env(ENV_DOMAIN)
    username = _first_env(ENV_USERNAME)
    password = _first_env(ENV_PASSWORD)
    cred_filepath = _first_env(ENV_CRED_FILEPATH)

    cred_file_usable = False
    if cred_filepath:
        if not Path(cred_filepath).is_file():
            raise RuntimeError(
                f"Configured credential file '{cred_filepath}' does not exist. "
                "Set OSW_CRED_FILEPATH (or its OSW_MCP_CRED_FILEPATH / "
                "OSL_CRED_FILEPATH aliases) to a valid path, or remove it and "
                "configure OSW_USERNAME/OSW_PASSWORD instead."
                + _escape_hint(cred_filepath)
            )
        cred_file_usable = True

    # A usable credential file makes the domain optional: which instance to
    # use is then chosen later (auto-selected, or via the CLI's --instance).
    checks = []
    if not cred_file_usable:
        checks.append((ENV_DOMAIN, domain))
        checks.append((ENV_USERNAME, username))
        checks.append((ENV_PASSWORD, password))
    missing = [names[0] for names, value in checks if not value]
    if missing and strict:
        raise RuntimeError(
            "Missing required OSW credential environment variables: "
            + ", ".join(missing)
            + ". Set them in your environment or a .env file "
            "(pointed to by OSW_ENV_FILE / OSW_MCP_ENV_FILE), or configure a "
            "credential file via OSW_CRED_FILEPATH (or its OSW_MCP_CRED_FILEPATH "
            "/ OSL_CRED_FILEPATH aliases). The server refuses to start without "
            "them to avoid an interactive credential prompt that would hang "
            "the stdio transport."
        )

    if cred_file_usable and domain:
        _verify_cred_file_has_domain(cred_filepath, domain)

    kwargs: dict = dict(
        domain=domain,
        username=username,
        password=password,
        cred_filepath=cred_filepath,
        sparql_endpoint=_first_env(ENV_SPARQL_ENDPOINT),
        state_dir=_first_env(ENV_STATE_DIR),
    )
    # An unset or blank/whitespace-only variable falls back to the model
    # default; pass the raw string only when there is one to validate. Letting
    # pydantic parse read_only rather than testing membership in a truthy set
    # matters because the default is fail-open: a typo like "ture" would
    # otherwise silently leave writes enabled on a server meant to be read-only.
    read_only_raw = _first_env(ENV_READ_ONLY)
    if read_only_raw is not None and read_only_raw.strip():
        kwargs["read_only"] = read_only_raw
    max_results_raw = _first_env(ENV_MAX_RESULTS)
    if max_results_raw is not None and max_results_raw.strip():
        kwargs["max_results"] = max_results_raw
    max_chars_raw = _first_env(ENV_MAX_CHARS)
    if max_chars_raw is not None and max_chars_raw.strip():
        kwargs["max_chars"] = max_chars_raw

    try:
        return Settings(**kwargs)
    except ValidationError as exc:
        details = []
        for err in exc.errors():
            field_name = str(err["loc"][0]) if err["loc"] else "<config>"
            details.append(
                f"{_env_name_for(field_name)}={err.get('input')!r}: {err['msg']}"
            )
        raise RuntimeError("Invalid OSW configuration: " + "; ".join(details)) from exc


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
    global _discover_env_file, _env_file_path, _env_file_origin
    _settings = None
    _active_iri = None
    _active_resolved = False
    _discover_env_file = False
    _env_file_path = None
    _env_file_origin = "not searched"


# -- active-instance state ---------------------------------------------------
#
# A server can be configured with several candidate instances (an
# env-configured domain and/or the iris in a credential file). Exactly one of
# them is "active" at a time; tools connect to whichever one is active. The
# active instance is auto-selected on first access (see ``_auto_select_iri``)
# and can be changed via ``set_active_instance`` (the CLI's ``--instance``
# flag; the MCP server is pinned to one instance and never switches).

_active_iri: Optional[str] = None
_active_resolved: bool = False


def _auto_select_iri() -> Optional[str]:
    """Auto-select the active iri, or return ``None`` if none can be chosen.

    1. A domain configured via the environment is always the active instance.
    2. Otherwise, if a credential file is configured and contains exactly one
       iri, that iri is the active instance.
    3. Otherwise there is no active instance until ``set_active_instance`` is
       called (e.g. via the CLI's ``--instance`` flag).
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
