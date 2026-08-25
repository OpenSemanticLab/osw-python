"""Guard tests: no filesystem path may ever reach the MCP surface.

Runs in the plain dev env (no mcp extra needed): importing ``osw.cli.ops``
(to register the CLI-only, path-taking operations, so the negative check
below cannot pass vacuously) and ``osw.service.ops`` touches neither the
``mcp`` SDK nor the network. Only ``test_mcp_server_never_imports_cli``
needs the ``mcp`` extra (it imports ``osw.mcp.server`` itself), and
self-skips without it.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

# Registers every operation, including the CLI-only path-taking ones, so
# osw.service.registry.REGISTRY is fully populated for the checks below.
import osw.cli.ops
import osw.service.ops  # noqa: F401
from osw.service.config import Settings
from osw.service.context import Context, Policy
from osw.service.registry import PATH_LIKE_NAMES, REGISTRY, bind, iter_operations

_CLI_ONLY_PATH_OPS = {"download_file", "upload_file"}


def _params(fn):
    """The op's parameters, minus ``ctx``."""
    return list(inspect.signature(fn).parameters.values())[1:]


def test_no_mcp_operation_names_a_path():
    mcp_ops = list(iter_operations(surface="mcp"))
    assert mcp_ops, "expected at least one operation on the mcp surface"

    for op in mcp_ops:
        offending = [p.name for p in _params(op.fn) if p.name in PATH_LIKE_NAMES]
        assert not offending, f"{op.name}: path-like parameter(s) {offending}"

    # The assertion above must not pass vacuously: the CLI-only download/
    # upload operations DO name a path, and must NOT appear on the mcp
    # surface.
    mcp_names = {op.name for op in mcp_ops}
    assert not (_CLI_ONLY_PATH_OPS & mcp_names)

    cli_ops_by_name = {op.name: op for op in iter_operations(surface="cli")}
    for name in _CLI_ONLY_PATH_OPS:
        assert name in cli_ops_by_name, f"expected {name!r} to be registered"
        op = cli_ops_by_name[name]
        param_names = {p.name for p in _params(op.fn)}
        assert param_names & PATH_LIKE_NAMES, (
            f"{name}: expected at least one path-like parameter"
        )
        assert "mcp" not in op.surfaces


def test_bound_operations_do_not_expose_ctx():
    ctx = Context(
        Settings(domain="wiki.example.org", username="u", password="p"),
        Policy(),
        osw=MagicMock(),
        ledger=MagicMock(),
    )
    assert REGISTRY, "expected the registry to be populated"
    for op in REGISTRY.values():
        bound = bind(op, ctx)
        assert "ctx" not in inspect.signature(bound).parameters


def test_mcp_server_never_imports_cli():
    pytest.importorskip("mcp", reason="requires the osw[mcp] extra")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\n"
            "import osw.mcp.server\n"
            "leaked = [m for m in sys.modules if m == 'osw.cli' "
            "or m.startswith('osw.cli.')]\n"
            "print('LEAKED:' + ','.join(leaked) if leaked else 'CLEAN')\n",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    # Importing osw prints unrelated hints (e.g. about the wikitext extra) on
    # stdout, so match the sentinel line rather than the whole stream.
    sentinel = [
        line
        for line in result.stdout.splitlines()
        if line.startswith(("CLEAN", "LEAKED:"))
    ]
    assert sentinel == ["CLEAN"], result.stdout + result.stderr
