"""CLI-only operations that name a filesystem path.

This is the only module in the codebase allowed to do so: every operation
here declares ``surfaces=frozenset({"cli"})``, so none of it is ever visible
to ``iter_operations(surface="mcp")`` and the registry's path-name validator
never even runs against it (that validator only inspects the ``mcp``
surface). A path argument is meaningful here because the CLI runs under the
invoking user's own shell permissions; it would be meaningless -- or a
filesystem escape hatch -- on an MCP client that may not share a host with
the server.

Imported by ``osw.cli.main`` (and nowhere else) before the command-tree loop,
so these commands are registered without ``osw.mcp`` ever importing this
module.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from osw.controller.file.wiki import WikiFileController
from osw.core import OverwriteOptions
from osw.service import config, errors
from osw.service.context import Context
from osw.service.ledger import LedgerRecord
from osw.service.registry import operation
from osw.utils.wiki import title_from_full_title
from osw.wtsite import WtSite

_logger = logging.getLogger(__name__)


class _RenamedFile:
    """Proxy over a file object that allows overriding its ``.name``.

    ``WikiFileController.put()`` derives the upload's suffix/label from
    ``file.name``, but a real ``open()``-returned file object's ``.name`` (its
    open-time path) is not a writable attribute. This proxy delegates
    everything else to the wrapped file object.
    """

    def __init__(self, fh, name: str) -> None:
        self._fh = fh
        self.name = name

    def __getattr__(self, item):
        return getattr(self._fh, item)


def _file_controller(ctx: Context, title: Optional[str] = None) -> WikiFileController:
    """Build a ``WikiFileController``, optionally bound to a full title."""
    if title:
        return WikiFileController(
            osw=ctx.osw, title=title_from_full_title(title), namespace="File"
        )
    return WikiFileController(osw=ctx.osw)


@operation(
    group="file",
    cli_name="download",
    surfaces=frozenset({"cli"}),
    read_only_hint=True,
    idempotent_hint=True,
)
def download_file(
    ctx: Context,
    title: str,
    target_dir: Optional[str] = None,
    overwrite: bool = False,
) -> dict:
    """Download a wiki file to the local filesystem.

    ``title`` is a full ``File:`` page title. Streams the file in chunks so a
    large file never lands in memory at once.
    """
    page = ctx.osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
    if not page.exists:
        raise errors.NotFound(f"File '{title}' does not exist.")

    wf = _file_controller(ctx, title)
    dest_dir = Path(target_dir) if target_dir else Path.cwd()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / wf.title
    if dest_path.exists() and not overwrite:
        raise FileExistsError(
            f"'{dest_path}' already exists. Pass --overwrite to replace it."
        )
    stream = wf.get()
    try:
        with open(dest_path, "wb") as fh:
            shutil.copyfileobj(stream, fh)
    finally:
        stream.close()
    return {"title": title, "path": str(dest_path)}


@operation(
    group="file",
    cli_name="upload",
    surfaces=frozenset({"cli"}),
    writes=True,
    destructive_hint=False,
    idempotent_hint=True,
    records=lambda r: [LedgerRecord(title=r["title"], op="create", slots=["jsondata"])],
)
def upload_file(
    ctx: Context,
    source_path: str,
    target_title: Optional[str] = None,
    name: Optional[str] = None,
    overwrite: bool = True,
) -> dict:
    """Upload a local file to the wiki as a WikiFile page.

    ``source_path`` is a path on the local disk. ``target_title`` is an
    optional full ``File:`` page title (otherwise auto-generated). Records
    the created page in the provenance ledger.
    """
    src = Path(source_path)
    if not src.is_file():
        raise errors.NotFound(f"Local file '{source_path}' does not exist.")

    wf = _file_controller(ctx, target_title)
    overwrite_opt = OverwriteOptions.true if overwrite else OverwriteOptions.false
    with open(src, "rb") as fh:
        stream = _RenamedFile(fh, name or src.name)
        wf.put(stream, overwrite=overwrite_opt)

    return {
        "title": f"{wf.namespace}:{wf.title}",
        "url": wf.url,
    }


@operation(
    group="ledger",
    cli_name="path",
    surfaces=frozenset({"cli"}),
    read_only_hint=True,
    idempotent_hint=True,
)
def ledger_path(ctx: Context) -> dict:
    """Print the local path of the provenance ledger file for the active instance."""
    return {"path": str(ctx.ledger.path)}


@operation(
    group="skill",
    cli_name="install",
    surfaces=frozenset({"cli"}),
    idempotent_hint=True,
)
def install_skill(
    ctx: Context,
    name: str = "osl-tasks",
    target_dir: Optional[str] = None,
    force: bool = False,
) -> dict:
    """Install a Claude Code skill that ships with this package.

    Copies the packaged skill directory ``src/osw/skills/<name>`` to
    ``~/.claude/skills/<name>`` (or under ``target_dir`` when given). A new
    Claude Code session picks the installed skill up automatically, with no
    further action needed. This is the alternative to installing the
    osw-python plugin from its marketplace.
    """
    src = Path(__file__).resolve().parent.parent / "skills" / name
    if not src.is_dir():
        available = sorted(p.name for p in src.parent.iterdir() if p.is_dir())
        raise errors.NotFound(
            f"No packaged skill named '{name}'. Available: {', '.join(available)}."
        )

    base = Path(target_dir) if target_dir else Path.home() / ".claude" / "skills"
    dest = base / name
    if dest.exists() and not force:
        raise errors.OpError(f"'{dest}' already exists. Pass --force to overwrite it.")

    shutil.copytree(src, dest, dirs_exist_ok=True)
    files = sorted(
        p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()
    )
    return {"name": name, "source": str(src), "target": str(dest), "files": files}


@operation(
    group="instances",
    cli_name="list",
    surfaces=frozenset({"cli"}),
    read_only_hint=True,
    idempotent_hint=True,
)
def list_instances(ctx: Context) -> dict:
    """List the OSL instances this process can connect to.

    Reports the iris available from the env-configured domain and/or a
    configured credential file, and which one (if any) is currently active
    for this invocation (see --instance). Never returns usernames, passwords,
    or any other credential value.
    """
    return {
        "iris": config.available_iris(),
        "active_iri": config.get_active_iri(),
        "active_domain": config.get_active_domain(),
    }


def _close_quietly(connection, iri: str) -> None:
    """Close a throwaway connection, reporting a failure without raising.

    Mirrors :meth:`osw.service.context.Context.reset`. Failing to close a
    connection says nothing about whether it was reachable, so it must not
    turn a successful check into a reported connection error.
    """
    try:
        connection.close_connection()
    except Exception as exc:
        _logger.warning(f"[osw] error closing connection to {iri}: {exc!r}")


@operation(
    group="instances",
    cli_name="status",
    surfaces=frozenset({"cli"}),
    read_only_hint=True,
    idempotent_hint=True,
)
def status_instances(ctx: Context) -> dict:
    """Report connection status for every configured OSL instance.

    Iterates every iri from :func:`osw.service.config.available_iris` (the
    env-configured domain plus every iri in a configured credential file) and
    checks each one independently, so a user with several endpoints in a
    credential file can check them all in one command. One failing instance
    does not stop the check of the others. Never returns passwords, or any
    other credential value.

    The instances are checked one after another and a single check has no
    timeout (see the probe in :mod:`osw.express`), so an unreachable instance
    holds the command up for as long as its connection attempt takes.
    """
    iris = config.available_iris()
    if not iris:
        return {
            "instances": [],
            "count": 0,
            "message": (
                "No OSL instance configured. For a server process, set "
                "OSW_DOMAIN (or OSW_ENV_FILE to point at a .env file that "
                "sets it); for the CLI, pass --instance <iri>."
            ),
        }
    active_iri = config.get_active_iri()
    instances = []
    for iri in iris:
        entry = {
            "iri": iri,
            "active": iri == active_iri,
            "username": None,
            "connected": False,
        }
        # Everything that can fail for one instance stays inside this try, so
        # the remaining instances are still checked.
        try:
            entry["username"] = config.get_credentials_for(iri)[0]
            with ctx.guard():
                # Not ctx.osw: that one is cached and bound to the active
                # instance. These connections are ours alone, so we close each
                # one instead of leaving it open for the rest of the command.
                connection = ctx.osw_for(config.derive_domain(iri))
                entry["connected"] = True
                _close_quietly(connection, iri)
        except Exception as exc:
            entry["error"] = str(exc)
        instances.append(entry)
    return {"instances": instances, "count": len(instances)}
