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
from osw.defaults import CRED_FILENAME_DEFAULT

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
ENV_VERBOSE = ("OSW_VERBOSE", "OSW_MCP_VERBOSE")


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
    "verbose": ENV_VERBOSE,
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
    # Only controls the startup configuration report. No tool or command
    # reads it, and Settings.redacted() deliberately does not expose it.
    verbose: bool = False

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

# Names that a .env file actually introduced (as opposed to names that were
# already set in the real environment and therefore left untouched, since
# load_dotenv() defaults to override=False). Used to tell the two apart in
# the startup banner. Accumulates across calls within a process, so a
# repeated _load_env_file() call cannot erase an earlier call's attribution;
# reset() clears it.
_env_file_supplied: set[str] = set()

# Where the credential file actually came from, for the startup banner. One
# of "environment", "env file", "default" (the accounts.pwd.yaml fallback),
# "none" (searched, nothing found) or "not searched". See _resolve_cred_file().
_cred_file_path: Optional[str] = None
_cred_file_origin: str = "not searched"
_cred_file_var: Optional[str] = None


def set_env_file_discovery(enabled: bool) -> None:
    """Enable or disable implicit discovery (default: disabled).

    This governs two searches of the current working directory, both skipped
    when disabled: the implicit ``.env`` search, and the ``accounts.pwd.yaml``
    credential file fallback in :func:`_resolve_cred_file`. Both searches
    depend on the working directory the process happens to run in, so both
    are gated by the same flag: the CLI's working directory is the one the
    user typed the command in, while the MCP server's is chosen by the MCP
    client, which it does not control.

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

    Also records, in ``_env_file_supplied``, every environment variable name
    that a ``.env`` file has introduced into this process (as opposed to
    names already set in the real environment, which ``load_dotenv()``'s
    default ``override=False`` leaves untouched). The set accumulates across
    calls, so a repeated call within the same process cannot erase an
    earlier call's attribution; :func:`reset` clears it.
    :func:`_resolve_cred_file` uses it to report whether a resolved
    credential path came from the file or from the real environment.
    """
    global _env_file_path, _env_file_origin, _env_file_supplied
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
        before = set(os.environ)
        dotenv.load_dotenv(path)
        _env_file_supplied |= set(os.environ) - before
        _env_file_path, _env_file_origin = path, "explicit"
        return
    if not _discover_env_file:
        return
    found = dotenv.find_dotenv(usecwd=True)
    if not found:
        _env_file_origin = "none"
        return
    before = set(os.environ)
    dotenv.load_dotenv(found)
    _env_file_supplied |= set(os.environ) - before
    _env_file_path, _env_file_origin = found, "discovered"


def _resolve_cred_file() -> Optional[str]:
    """Resolve the credential file path, in this order, and record its origin.

    1. An explicitly configured ``OSW_CRED_FILEPATH`` (or its
       ``OSW_MCP_CRED_FILEPATH`` / ``OSL_CRED_FILEPATH`` aliases) always wins,
       whether it came from the real environment or from a ``.env`` file.
       Existence is not checked here; ``load()`` already reports a missing
       configured file with a specific error message.
    2. Otherwise, if implicit discovery is disabled (the MCP server; see
       :func:`set_env_file_discovery`), nothing is resolved: origin
       ``"not searched"``.
    3. Otherwise, if either ``OSW_USERNAME`` or ``OSW_PASSWORD`` (or their
       ``OSL_*`` aliases) is already configured, nothing is resolved either:
       also ``"not searched"``. Any explicitly named credential means the
       operator intends to authenticate that way; a half-configured pair
       must produce a visible "missing variable" error rather than silently
       switch to a different identity via the fallback file.
    4. Otherwise, look for ``accounts.pwd.yaml`` in the current working
       directory (no walk to parent directories). If present, and a domain is
       configured, verify that the file has an entry for it
       (:func:`_verify_cred_file_has_domain`): if that fails, origin
       ``"rejected"`` and ``None`` is returned, but the path is kept in
       ``_cred_file_path`` so callers can still report which file was
       ignored. This is not fatal, unlike the same check for an explicitly
       configured file: the operator never named this file, they only
       happened to have one lying around, and :func:`load` accepts
       ``strict=False`` precisely so a status command can report "not
       configured" instead of crashing. If the file matches (or no domain is
       configured yet to check against), origin ``"default"``. If no such
       file exists, origin ``"none"``.

    So ``"not searched"`` has two distinct causes: discovery disabled, or
    username/password already configured. Safe to call more than once, like
    :func:`_load_env_file`, which this assumes has already run.
    """
    global _cred_file_path, _cred_file_origin, _cred_file_var
    path = _first_env(ENV_CRED_FILEPATH)
    if path:
        _cred_file_var = next(
            (n for n in ENV_CRED_FILEPATH if os.getenv(n) == path), ENV_CRED_FILEPATH[0]
        )
        _cred_file_origin = (
            "env file" if _cred_file_var in _env_file_supplied else "environment"
        )
        _cred_file_path = path
        return path
    if not _discover_env_file:
        _cred_file_path, _cred_file_origin, _cred_file_var = None, "not searched", None
        return None
    if _first_env(ENV_USERNAME) or _first_env(ENV_PASSWORD):
        _cred_file_path, _cred_file_origin, _cred_file_var = None, "not searched", None
        return None
    candidate = Path.cwd() / CRED_FILENAME_DEFAULT
    if candidate.is_file():
        domain = _first_env(ENV_DOMAIN)
        if domain:
            try:
                _verify_cred_file_has_domain(str(candidate), domain)
            except RuntimeError:
                _cred_file_path, _cred_file_origin, _cred_file_var = (
                    str(candidate),
                    "rejected",
                    None,
                )
                return None
        _cred_file_path, _cred_file_origin, _cred_file_var = (
            str(candidate),
            "default",
            None,
        )
        return str(candidate)
    _cred_file_path, _cred_file_origin, _cred_file_var = None, "none", None
    return None


def _describe_env_file() -> str:
    """Describe where the ``.env`` file came from, for the startup banner."""
    return {
        "explicit": f"{_env_file_path} (from {ENV_FILE[0]})",
        "discovered": f"{_env_file_path} (found from the working directory upward)",
        "none": "none found (searched from the working directory upward)",
        "not searched": f"not configured (set {ENV_FILE[0]} to use one)",
    }[_env_file_origin]


def log_config_sources(stream=None, verbose: bool = True) -> None:
    """Print where configuration was read from, to stderr.

    Loads the ``.env`` file first if that has not happened yet, and reads the
    environment directly rather than a ``Settings``. Both so this can run
    *before* settings are loaded: a misconfiguration makes loading raise, and
    that is exactly when knowing which files were read matters most.

    The credential line is printed first, since it is the one line that
    still appears when ``verbose`` is ``False``; the env-file line is then
    printed after it, only when ``verbose`` is ``True``. This keeps the two
    lines in the same relative order regardless of ``verbose``, including in
    the CLI's failure path, which prints the env-file line (via
    :func:`log_env_file_source`) after this one has already run.

    ``verbose`` defaults to ``True``, which keeps both lines. The CLI passes
    ``verbose=False`` for a successful, non-verbose command, and prints the
    env-file line separately (via :func:`log_env_file_source`) on failure or
    when the user passed ``--verbose``. The MCP server writes both lines to a
    buffer instead of stderr and shows them only when ``OSW_VERBOSE`` is set
    or the server fails to start.

    Writes to ``stderr``, or to ``stream`` when one is given, and never to
    ``stdout``: under MCP ``stdout`` carries the JSON-RPC stream, and under
    ``osw --json`` it carries the result payload.
    """
    _load_env_file()
    # Every print below flushes: stderr is block-buffered whenever it is not a
    # terminal (a pipe, a file, or a test runner's capture buffer), and these
    # lines must appear before the command's own output and before any error.
    out = sys.stderr if stream is None else stream
    _resolve_cred_file()
    if _cred_file_path:
        cred_described = {
            "environment": f"(from the {_cred_file_var} environment variable)",
            "env file": f"(from {_cred_file_var} in the env file)",
            "default": f"({CRED_FILENAME_DEFAULT} found in the working directory)",
            "rejected": (
                f"({CRED_FILENAME_DEFAULT} found in the working directory, "
                f"ignored: no entry for domain '{_first_env(ENV_DOMAIN)}')"
            ),
        }[_cred_file_origin]
        print(
            f"[osw] credential file: {_cred_file_path} {cred_described}",
            file=out,
            flush=True,
        )
    else:
        username = _first_env(ENV_USERNAME)
        password = _first_env(ENV_PASSWORD)
        if username or password:
            username_name = next((n for n in ENV_USERNAME if os.getenv(n)), None)
            password_name = next((n for n in ENV_PASSWORD if os.getenv(n)), None)
            from_env_file = (
                username_name in _env_file_supplied
                or password_name in _env_file_supplied
            )
            source = "from the env file" if from_env_file else "from the environment"
            cred_described = f"OSW_USERNAME/OSW_PASSWORD ({source})"
        else:
            cred_described = (
                "not configured (set OSW_CRED_FILEPATH, or OSW_USERNAME/OSW_PASSWORD)"
            )
        print(f"[osw] credentials    : {cred_described}", file=out, flush=True)
    if verbose:
        print(f"[osw] env file       : {_describe_env_file()}", file=out, flush=True)


def log_env_file_source(stream=None) -> None:
    """Print only the env-file line, for the CLI's failure path.

    Does *not* call :func:`_load_env_file`, so it is safe to call after
    :func:`load` has already raised: prints the line that
    ``log_config_sources(verbose=False)`` suppressed, using whatever
    ``_env_file_origin`` that earlier call already recorded.
    """
    out = sys.stderr if stream is None else stream
    print(f"[osw] env file       : {_describe_env_file()}", file=out, flush=True)


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
    actually contain an entry for the configured domain. When no credential
    file is configured, no username/password is set, and implicit discovery
    is enabled, an ``accounts.pwd.yaml`` file in the current working directory
    is used instead (see :func:`_resolve_cred_file`); this fallback never
    fires for the MCP server.

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
    cred_filepath = _resolve_cred_file()

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

    # A discovered file (origin "default") was already checked against the
    # domain inside _resolve_cred_file: a mismatch set origin "rejected" and
    # cleared cred_filepath there, so cred_file_usable is already False in
    # that case below. An explicitly configured file is different: the
    # operator named it, so a mismatch is still a hard error, unconditionally.
    discovered_file_discarded = _cred_file_origin == "rejected"
    if cred_file_usable and domain and _cred_file_origin != "default":
        _verify_cred_file_has_domain(cred_filepath, domain)

    # A usable credential file makes the domain optional: which instance to
    # use is then chosen later (auto-selected, or via the CLI's --instance).
    checks = []
    if not cred_file_usable:
        checks.append((ENV_DOMAIN, domain))
        checks.append((ENV_USERNAME, username))
        checks.append((ENV_PASSWORD, password))
    missing = [names[0] for names, value in checks if not value]
    if missing and strict:
        if discovered_file_discarded:
            fallback_hint = (
                " A file named 'accounts.pwd.yaml' was found in the current "
                f"working directory, but it has no entry for domain '{domain}'."
            )
        elif _discover_env_file:
            fallback_hint = (
                " Or place an 'accounts.pwd.yaml' file in the current working "
                "directory."
            )
        else:
            fallback_hint = ""
        # The stdio-hang rationale only applies to the MCP server: a CLI user
        # is not running a stdio server, so it would only confuse them.
        stdio_hint = (
            ""
            if _discover_env_file
            else (
                " The server refuses to start without them to avoid an "
                "interactive credential prompt that would hang the stdio "
                "transport."
            )
        )
        raise RuntimeError(
            "Missing required OSW credential environment variables: "
            + ", ".join(missing)
            + ". Set them in your environment or a .env file "
            "(pointed to by OSW_ENV_FILE / OSW_MCP_ENV_FILE), or configure a "
            "credential file via OSW_CRED_FILEPATH (or its OSW_MCP_CRED_FILEPATH "
            "/ OSL_CRED_FILEPATH aliases)." + fallback_hint + stdio_hint
        )

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
    verbose_raw = _first_env(ENV_VERBOSE)
    if verbose_raw is not None and verbose_raw.strip():
        kwargs["verbose"] = verbose_raw

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
    global _discover_env_file, _env_file_path, _env_file_origin, _env_file_supplied
    global _cred_file_path, _cred_file_origin, _cred_file_var
    _settings = None
    _active_iri = None
    _active_resolved = False
    _discover_env_file = False
    _env_file_path = None
    _env_file_origin = "not searched"
    _env_file_supplied = set()
    _cred_file_path = None
    _cred_file_origin = "not searched"
    _cred_file_var = None


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
