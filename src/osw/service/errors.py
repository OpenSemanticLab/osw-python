"""Stable-shaped operation errors shared by every osw.service adapter.

Every operation failure is an :class:`OpError` subclass carrying a wire
``type`` string (the shape an MCP client sees, unchanged from the
hand-written error dicts the tool bodies returned before this module
existed) and an ``exit_code`` (the process exit status a CLI adapter uses).

Exit codes are grouped by category, not unique per subclass:

* ``1`` -- generic / unexpected error (the ``OpError`` base default).
* ``2`` -- not found: a page/entity expected to exist does not
  (:class:`NotFound`).
* ``3`` -- invalid input: an argument is malformed, does not validate, or
  does not resolve (:class:`SchemaError`, :class:`ClassNotFound`,
  :class:`ValidationError`, :class:`UnknownInstance`, :class:`InvalidSlot`,
  :class:`InvalidContent`, :class:`SlotMissing`, :class:`BinaryContent`).
* ``4`` -- refused/blocked: disallowed by a provenance or safety guard
  (:class:`ExternalDeleteBlocked`, :class:`ReadOnly`).
* ``5`` -- not configured: required configuration is missing
  (:class:`NotConfigured`).
"""

from __future__ import annotations

from typing import Optional


class OpError(Exception):
    """Base for operation failures with a stable wire shape and a CLI exit code."""

    type: str = "Error"
    exit_code: int = 1

    def __init__(self, message: str, *, extra: Optional[dict] = None) -> None:
        super().__init__(message)
        self.extra: dict = dict(extra) if extra else {}

    def payload(self) -> dict:
        """The dict an MCP client receives. Must match today's shape exactly."""
        return {**self.extra, "error": str(self), "type": self.type}


class NotFound(OpError):
    """A page or entity that was expected to exist does not."""

    type = "NotFound"
    exit_code = 2


class SchemaError(OpError):
    """A category's schema could not be fetched."""

    type = "SchemaError"
    exit_code = 3


class ClassNotFound(OpError):
    """No generated model class could be resolved for a category."""

    type = "ClassNotFound"
    exit_code = 3


class ValidationError(OpError):
    """A ``jsondata`` payload does not validate against its category."""

    type = "ValidationError"
    exit_code = 3


class ExternalDeleteBlocked(OpError):
    """A delete was refused because the page was not created by this server."""

    type = "ExternalDeleteBlocked"
    exit_code = 4


class ReadOnly(OpError):
    """A write was refused because writes are disabled for this context."""

    type = "ReadOnly"
    exit_code = 4


class UnknownInstance(OpError):
    """A requested instance iri is not among the configured/available ones."""

    type = "UnknownInstance"
    exit_code = 3


class NotConfigured(OpError):
    """Required configuration is missing (e.g. an active instance, a SPARQL
    endpoint)."""

    type = "NotConfigured"
    exit_code = 5


class InvalidSlot(OpError):
    """A slot key is not one of the valid ``osw.wtsite.SLOTS`` keys."""

    type = "InvalidSlot"
    exit_code = 3


class InvalidContent(OpError):
    """A slot's content does not match its content model (json/wikitext)."""

    type = "InvalidContent"
    exit_code = 3


class SlotMissing(OpError):
    """A slot does not exist on a page and ``create_if_missing`` is false."""

    type = "SlotMissing"
    exit_code = 3


class BinaryContent(OpError):
    """A file's bytes do not decode under the requested text encoding.

    Raised by ``read_file_text`` when the requested file is not text; the mcp
    surface cannot return raw bytes, so the caller must use the CLI instead.
    """

    type = "BinaryContent"
    exit_code = 3
