"""Working-directory isolation for the integration tests."""

from pathlib import Path

import pytest

import osw.model.entity
from osw.defaults import paths as default_paths


@pytest.fixture(autouse=True, scope="session")
def _restore_entity_model():
    """Snapshot and restore src/osw/model/entity.py around the test session.

    OSW.fetch_schema regenerates the entity model INTO THE INSTALLED
    PACKAGE by design, which in an editable install is the source tree.
    Restoring the pre-session content keeps the working tree clean after
    `make test-integration` without relying on git or .gitignore.
    """
    model_file = Path(osw.model.entity.__file__)
    snapshot = model_file.read_bytes()
    yield
    if model_file.read_bytes() != snapshot:
        model_file.write_bytes(snapshot)
        print(f"\nRestored pre-session state of '{model_file}'.")


@pytest.fixture(autouse=True)
def _isolate_working_dir(tmp_path, monkeypatch):
    # covers every Path.cwd()-relative write in the tests themselves
    monkeypatch.chdir(tmp_path)
    # osw.defaults captures Path.cwd() at import time, so the singleton
    # still points into the repo; re-base it for the duration of the
    # test (setting `base` cascades to the dependent paths) and restore
    # the previous values afterwards.
    old = {
        "base": default_paths.base,
        "osw_files_dir": default_paths.osw_files_dir,
        "cred_filepath": default_paths.cred_filepath,
        "download_dir": default_paths.download_dir,
    }
    default_paths.base = tmp_path
    yield
    for name, value in old.items():
        setattr(default_paths, name, value)
