"""Output stream setup shared by the osw CLI and the osw-mcp server.

Neither adapter may import the other, and both write text that the locale
encoding may not be able to represent. The single helper here is what they
share; which streams to apply it to is the caller's decision, because the two
adapters differ there. See :func:`force_utf8`.
"""

from __future__ import annotations

from typing import TextIO


def force_utf8(*streams: TextIO) -> None:
    """Encode each given stream as UTF-8, whatever the locale asks for.

    Python encodes a redirected stream with the locale encoding, which on a
    German Windows system is cp1252. A non-ASCII label then reaches the
    consumer as bytes no JSON parser can read, and a character cp1252 has no
    code point for -- Japanese, Greek, Cyrillic -- raises UnicodeEncodeError
    and ends the command. A Windows console stream is UTF-8 already, so on
    Windows only redirected output changes. Elsewhere a terminal uses the
    locale encoding, so this overrides a deliberate non-UTF-8 LANG or
    PYTHONIOENCODING too.

    Each stream is reconfigured in place. A ``logging.StreamHandler`` built
    earlier holds the stream object itself, not a name, so it writes UTF-8
    from here on as well.
    """
    for stream in streams:
        reconfigure = getattr(stream, "reconfigure", None)
        errors = getattr(stream, "errors", None)
        # A stream a test harness or host application substituted may have
        # neither, and then decides its own encoding. Both are required:
        # errors= must be passed, because reconfigure() silently resets the
        # handler to strict otherwise, which would let stderr raise while
        # reporting a failure. Passing errors=None does exactly that too.
        if reconfigure is not None and errors is not None:
            reconfigure(encoding="utf-8", errors=errors)
