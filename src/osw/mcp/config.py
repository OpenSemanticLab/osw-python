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
from typing import Optional

# python-dotenv is part of the [mcp] extra
from dotenv import load_dotenv

_TRUTHY = {"1", "true", "yes", "on"}

# Environment variable names (OSL_* are accepted as fallbacks, matching osw).
ENV_DOMAIN = ("OSW_DOMAIN", "OSL_DOMAIN")
ENV_USERNAME = ("OSW_USERNAME", "OSL_USERNAME")
ENV_PASSWORD = ("OSW_PASSWORD", "OSL_PASSWORD")


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

    domain: str
    username: str
    # kept only to build the SPARQL client; never returned by any tool
    password: str = field(repr=False)
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


def load() -> Settings:
    """Load and validate settings from the environment.

    Loads a ``.env`` file first: the path in ``OSW_MCP_ENV_FILE`` if set,
    otherwise dotenv's default search from the current working directory upward.

    Raises
    ------
    RuntimeError
        If any of domain / username / password is missing, so the osw
        interactive credential prompt is never reached.
    """
    env_file = os.getenv("OSW_MCP_ENV_FILE")
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    domain = _first_env(ENV_DOMAIN)
    username = _first_env(ENV_USERNAME)
    password = _first_env(ENV_PASSWORD)

    missing = [
        names[0]
        for names, value in (
            (ENV_DOMAIN, domain),
            (ENV_USERNAME, username),
            (ENV_PASSWORD, password),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing required OSW credential environment variables: "
            + ", ".join(missing)
            + ". Set them in your environment or a .env file "
            "(pointed to by OSW_MCP_ENV_FILE). The server refuses to start "
            "without them to avoid an interactive credential prompt that would "
            "hang the stdio transport."
        )

    return Settings(
        domain=domain,
        username=username,
        password=password,
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
    """Drop cached settings (used by tests)."""
    global _settings
    _settings = None
