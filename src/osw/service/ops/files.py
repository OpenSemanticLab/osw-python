"""Path-free wiki file content operations: info, read, write.

``WikiFileController.get()`` returns a live stream and ``.put()`` accepts one
(see ``osw.controller.file.wiki``), so these operations never touch the local
filesystem: content moves between the wiki and the caller entirely in
memory, in bounded chunks. Path-taking counterparts (download to disk, upload
from disk) live in ``osw.cli.ops``, the only module allowed to name a path.
"""

from __future__ import annotations

import codecs
from io import BytesIO
from typing import Optional

from osw.controller.file.wiki import WikiFileController
from osw.core import OverwriteOptions
from osw.service import errors
from osw.service.context import Context
from osw.service.ledger import LedgerRecord
from osw.service.registry import operation
from osw.utils.wiki import title_from_full_title
from osw.wtsite import WtSite


def _file_controller(ctx: Context, title: str) -> WikiFileController:
    """Build a ``WikiFileController`` bound to ``title`` (a full ``File:`` title)."""
    return WikiFileController(
        osw=ctx.osw, title=title_from_full_title(title), namespace="File"
    )


@operation(
    group="file",
    cli_name="info",
    read_only_hint=True,
    idempotent_hint=True,
)
def get_file_info(ctx: Context, title: str) -> dict:
    """Return a wiki file's metadata: url, existence, size and media type.

    ``title`` is a full ``File:`` page title. Reads only the headers of the
    same download stream ``read_file_text`` uses; the file's content is
    never pulled into memory.
    """
    page = ctx.osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
    if not page.exists:
        return {
            "title": title,
            "exists": False,
            "url": None,
            "size": None,
            "media_type": None,
        }

    wf = _file_controller(ctx, title)
    stream = wf.get()
    try:
        size = stream.headers.get("Content-Length")
        media_type = stream.headers.get("Content-Type")
    finally:
        stream.close()
    return {
        "title": title,
        "exists": True,
        "url": wf.url,
        "size": int(size) if size is not None else None,
        "media_type": media_type,
    }


@operation(
    group="file",
    cli_name="cat",
    read_only_hint=True,
    idempotent_hint=True,
)
def read_file_text(
    ctx: Context, title: str, encoding: str = "utf-8", limit: Optional[int] = None
) -> dict:
    """Read a wiki file's content as text, returned inline in the result.

    Reads at most ``limit`` (or the server's configured max_chars) bytes plus
    one, so an oversized file is never pulled fully into memory; truncation
    is reported in the result rather than silently dropping content. If the
    bytes do not decode under ``encoding``, use ``osw file download`` instead
    to fetch the file to disk.
    """
    page = ctx.osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
    if not page.exists:
        raise errors.NotFound(f"File '{title}' does not exist.")

    cap = limit if limit is not None else ctx.settings.max_chars
    wf = _file_controller(ctx, title)
    stream = wf.get()
    try:
        raw = stream.read(cap + 1)
    finally:
        stream.close()
    truncated = len(raw) > cap
    if truncated:
        raw = raw[:cap]
    try:
        # Decoded incrementally, with final=False when the read was capped:
        # `cap` counts bytes, so truncating can split a multi-byte character.
        # A plain bytes.decode() would raise on that trailing fragment and a
        # perfectly valid text file would be reported as binary. final=False
        # buffers the fragment (and so discards it) while still raising on
        # bytes that are genuinely undecodable.
        content = codecs.getincrementaldecoder(encoding)().decode(raw, not truncated)
    except UnicodeDecodeError as exc:
        raise errors.BinaryContent(
            f"File '{title}' is not valid {encoding} text; use "
            "`osw file download` instead to fetch it to disk."
        ) from exc
    return {
        "title": title,
        "content": content,
        "encoding": encoding,
        "truncated": truncated,
    }


@operation(
    group="file",
    cli_name="write",
    writes=True,
    destructive_hint=False,
    idempotent_hint=True,
    records=lambda r: [LedgerRecord(title=r["title"], op="create", slots=["jsondata"])],
)
def write_file_text(
    ctx: Context,
    title: str,
    content: str,
    name: Optional[str] = None,
    overwrite: bool = True,
) -> dict:
    """Write text content to a wiki file page, creating or overwriting it.

    ``title`` is a full ``File:`` page title. ``name`` sets the uploaded
    file's base name (defaults to the bare filename portion of ``title``).
    Records the page in the provenance ledger.
    """
    wf = _file_controller(ctx, title)
    stream = BytesIO(content.encode("utf-8"))
    stream.name = name or title_from_full_title(title)
    overwrite_opt = OverwriteOptions.true if overwrite else OverwriteOptions.false
    wf.put(stream, overwrite=overwrite_opt)
    return {
        "title": f"{wf.namespace}:{wf.title}",
        "url": wf.url,
    }
