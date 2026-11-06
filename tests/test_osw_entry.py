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

# Every subprocess below is read with these. text=True alone decodes with the
# locale encoding, which on a German Windows system is cp1252, and the reader
# thread then raises UnicodeDecodeError on the box-drawing bytes rich writes
# into --help output. The exception happens in the thread, so the test still
# passes and only a PytestUnhandledThreadExceptionWarning shows it. Decoding
# as UTF-8 matches what the child actually writes. errors="replace" keeps a
# byte outside UTF-8 from ending a test, which is safe because every
# assertion here searches for ASCII text.
_DECODE = {"text": True, "encoding": "utf-8", "errors": "replace"}


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
        **_DECODE,
        env=_env_without_log_level(),
    )

    assert result.returncode == 0, result.stderr
    assert not any(NOTICE in line for line in result.stderr.splitlines())


def test_the_osw_console_script_version_flag_prints_only_the_version_line():
    """--version must not carry the import notice either, and nothing else
    on stdout (Change: issue #199)."""
    result = subprocess.run(
        [_console_script("osw"), "--version"],
        capture_output=True,
        **_DECODE,
        env=_env_without_log_level(),
    )

    assert result.returncode == 0, result.stderr
    assert not any(NOTICE in line for line in result.stderr.splitlines())
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("osw ")


def test_importing_osw_directly_still_prints_the_notice_on_stderr():
    """Without the shim, library behaviour is unchanged: the notice is still
    written, proving the console script above is quiet because of osw_entry
    and not because the notice stopped firing altogether."""
    result = subprocess.run(
        [sys.executable, "-c", "import osw"],
        capture_output=True,
        **_DECODE,
        env=_env_without_log_level(),
    )

    assert result.returncode == 0, result.stderr
    assert any(NOTICE in line for line in result.stderr.splitlines())


def test_the_osw_mcp_console_script_stays_quiet_and_leaves_stdout_empty():
    """The second console script needs its own check, because it is the one
    where a stray line is destructive rather than untidy.

    osw-mcp speaks JSON-RPC over stdout. A single non-JSON line there breaks
    the client's parser. The notice goes to stderr today, so the risk is
    about a future change moving it, which is what the stdout assertion
    catches. Dummy credentials are enough: building the server does not
    contact the wiki. Empty stdin gives the transport an immediate EOF, so
    the server serves nothing and exits by itself.
    """
    env = _env_without_log_level()
    # Set explicitly so the run does not depend on the developer's own
    # configuration, and so it can never reach a real wiki.
    env.pop("OSW_ENV_FILE", None)
    env.pop("OSW_CRED_FILEPATH", None)
    env["OSW_DOMAIN"] = "wiki.example.org"
    env["OSW_USERNAME"] = "not-a-real-user"
    env["OSW_PASSWORD"] = "not-a-real-secret"
    env["OSW_READ_ONLY"] = "true"

    result = subprocess.run(
        [_console_script("osw-mcp")],
        input="",
        capture_output=True,
        **_DECODE,
        env=env,
        timeout=180,
    )

    assert result.returncode == 0, result.stderr
    assert not any(NOTICE in line for line in result.stderr.splitlines())
    assert result.stdout.strip() == ""


def test_the_level_the_shim_sets_is_osws_own_default():
    """osw_entry writes the level name out instead of importing it, so a
    change to osw.DEFAULT_LOG_LEVEL would otherwise leave the shim setting a
    different level than osw would have picked, and silently change what the
    console scripts log."""
    import logging

    import osw
    import osw_entry

    assert logging.getLevelName(osw.DEFAULT_LOG_LEVEL) == osw_entry._DEFAULT_LEVEL


def test_the_helper_does_not_override_an_already_set_log_level(monkeypatch):
    """setdefault is what makes this safe: a value the caller chose on
    purpose must survive, since overriding it would silently change what the
    caller asked osw to log at."""
    monkeypatch.setenv("OSW_LOG_LEVEL", "DEBUG")
    import osw_entry

    osw_entry._suppress_import_notice()

    assert os.environ["OSW_LOG_LEVEL"] == "DEBUG"
