"""Pins that every file controller keeps the OSW category of its wrapped model.

A controller's 'type' field decides which wiki category an entity is stored
under. If a controller does not redefine 'type', it can silently inherit a
different category from earlier in its MRO, filing pages under the wrong
class.
"""

import osw.model.entity as model
from osw.controller.file.base import FileController
from osw.controller.file.local import LocalFileController
from osw.controller.file.memory import InMemoryController
from osw.controller.file.wiki import WikiFileController


def test_file_controller_keeps_files_category():
    assert (
        FileController.__fields__["type"].get_default()
        == model.File.__fields__["type"].get_default()
    )


def test_local_file_controller_keeps_local_files_category():
    assert (
        LocalFileController.__fields__["type"].get_default()
        == model.LocalFile.__fields__["type"].get_default()
    )


def test_in_memory_controller_keeps_local_files_category():
    """Same base order as LocalFileController, so the same category applies."""
    assert (
        InMemoryController.__fields__["type"].get_default()
        == model.LocalFile.__fields__["type"].get_default()
    )


def test_wiki_file_controller_keeps_wiki_files_category():
    assert (
        WikiFileController.__fields__["type"].get_default()
        == model.WikiFile.__fields__["type"].get_default()
    )
