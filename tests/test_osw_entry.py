"""Offline tests for osw_entry, the shim behind the osw and osw-mcp console
scripts.

osw writes a one-off notice to stderr at import time (see
src/osw/__init__.py), unless OSW_LOG_LEVEL is already in the environment.
osw_entry sets that variable before osw is imported, so the console scripts
stay quiet while a plain `import osw` still gets the notice. Nothing inside
the osw package could do this itself: importing any of its submodules
imports the package first, and the notice would already be written by then.
So this has to be proven with a real subprocess, one for each side of the
comparison, rather than by importing osw in this process.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

NOTICE = "osw logs at INFO"


def _console_script(name: str) -> str:
    """Path to a console script installed next to the running interpreter."""
    suffix = ".exe" if os.name == "nt" else ""
    return str(Path(sys.executable).parent / f"{name}{suffix}")


def _env_without_log_level() -> dict:
    """A copy of the environment with OSW_LOG_LEVEL removed, so a subprocess
    starts exactly as an interpreter that never set it would."""
    env = dict(os.environ)
    env.pop("OSW_LOG_LEVEL", None)
    return env


def test_the_osw_console_script_does_not_print_the_import_notice_on_stderr():
    """The shim sets OSW_LOG_LEVEL before osw is imported, so the console
    script stays quiet even though the environment it starts from does not
    set the variable itself."""
    result = subprocess.run(
        [_console_script("osw"), "--help"],
        capture_output=True,
        text=True,
        env=_env_without_log_level(),
    )

    assert result.returncode == 0, result.stderr
    assert not any(NOTICE in line for line in result.stderr.splitlines())


def test_importing_osw_directly_still_prints_the_notice_on_stderr():
    """Without the shim, library behaviour is unchanged: the notice is still
    written, proving the console script above is quiet because of osw_entry
    and not because the notice stopped firing altogether."""
    result = subprocess.run(
        [sys.executable, "-c", "import osw"],
        capture_output=True,
        text=True,
        env=_env_without_log_level(),
    )

    assert result.returncode == 0, result.stderr
    assert any(NOTICE in line for line in result.stderr.splitlines())


def test_the_helper_does_not_override_an_already_set_log_level(monkeypatch):
    """setdefault is what makes this safe: a value the caller chose on
    purpose must survive, since overriding it would silently change what the
    caller asked osw to log at."""
    monkeypatch.setenv("OSW_LOG_LEVEL", "DEBUG")
    import osw_entry

    osw_entry._suppress_import_notice()

    assert os.environ["OSW_LOG_LEVEL"] == "DEBUG"
