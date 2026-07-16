"""File tools: download a file to local disk, upload a local file to the wiki."""

from __future__ import annotations

from typing import Optional

from osw.core import OverwriteOptions

from ..connection import get_ledger, run_guarded


def register(mcp, *, include_writes: bool) -> None:
    """Register file tools; the uploader only when ``include_writes``."""

    @mcp.tool()
    def download_file(
        title_or_url: str,
        target_dir: Optional[str] = None,
        overwrite: bool = False,
    ) -> dict:
        """Download a WikiFile to the local disk.

        ``title_or_url`` is a ``File:`` full page title or a file URL. Writes only
        to the local filesystem (no wiki mutation). Returns the local path.
        """

        def _run(osw):
            result = osw.download_file(
                title_or_url, target_dir=target_dir, overwrite=overwrite
            )
            return {
                "title": title_or_url,
                "path": str(result.path) if result.path is not None else None,
            }

        return run_guarded(_run)

    if not include_writes:
        return

    @mcp.tool()
    def upload_file(
        source_path: str,
        target_title: Optional[str] = None,
        overwrite: bool = True,
        name: Optional[str] = None,
    ) -> dict:
        """Upload a local file to the wiki as a WikiFile page.

        ``source_path`` is a path on the local disk. ``target_title`` is an
        optional ``File:`` full page title (otherwise auto-generated). Records
        the created page in the provenance ledger.
        """
        ledger = get_ledger()
        overwrite_opt = OverwriteOptions.true if overwrite else OverwriteOptions.false

        def _run(osw):
            kwargs = {}
            if name:
                kwargs["name"] = name
            result = osw.upload_file(
                source=source_path,
                url_or_title=target_title,
                overwrite=overwrite_opt,
                **kwargs,
            )
            title = (
                getattr(result, "target_fpt", None)
                or getattr(result, "url_or_title", None)
                or getattr(result, "title", None)
            )
            try:
                url = result.get_url()
            except Exception:
                url = getattr(result, "url", None)
            change_id = getattr(result, "change_id", None)
            if title:
                ledger.record(
                    title,
                    op="create",
                    tool="upload_file",
                    change_id=change_id,
                    slots=["jsondata"],
                )
            return {"title": title, "url": url, "change_id": change_id}

        return run_guarded(_run)
