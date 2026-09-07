"""Offline tests for the target filename of osw.express downloads.

Covers #94: a download can keep the OSW-ID it has on the wiki, use the original
file name, or combine both.
"""

import pytest

from osw.express import FilenameMode, build_target_fn

OSW_ID_FN = "OSW02a0e8a917594129b3b8f2f48e2c3f7f.txt"


@pytest.mark.parametrize("mode", [FilenameMode.osw_id, "osw_id"])
def test_osw_id_mode_keeps_the_wiki_filename(mode):
    """The default, unchanged from before the modes existed."""
    assert build_target_fn(mode, OSW_ID_FN, "My_textfile") == OSW_ID_FN


def test_name_mode_uses_the_original_name():
    assert build_target_fn(FilenameMode.name, OSW_ID_FN, "My_textfile") == (
        "My_textfile.txt"
    )


def test_name_and_osw_id_mode_uses_both():
    assert build_target_fn(FilenameMode.name_and_osw_id, OSW_ID_FN, "My_textfile") == (
        "My_textfile_OSW02a0e8a917594129b3b8f2f48e2c3f7f.txt"
    )


@pytest.mark.parametrize(
    "mode", [FilenameMode.name, FilenameMode.name_and_osw_id, FilenameMode.osw_id]
)
def test_every_suffix_is_carried_over(mode):
    """The OSW-ID carries no dot, so '.drawio.png' is one suffix, not two."""
    osw_id_fn = "OSW02a0e8a917594129b3b8f2f48e2c3f7f.drawio.png"

    assert build_target_fn(mode, osw_id_fn, "My_drawing").endswith(".drawio.png")


def test_a_name_that_still_carries_the_suffix_does_not_double_it():
    """WikiFileController strips the suffix off name, but not every page has it."""
    assert build_target_fn(FilenameMode.name, OSW_ID_FN, "My_textfile.txt") == (
        "My_textfile.txt"
    )


def test_dots_inside_the_name_are_kept():
    assert build_target_fn(FilenameMode.name, OSW_ID_FN, "v1.2.3_report") == (
        "v1.2.3_report.txt"
    )


def test_a_file_without_a_suffix_gets_none():
    osw_id_fn = "OSW02a0e8a917594129b3b8f2f48e2c3f7f"

    assert build_target_fn(FilenameMode.name, osw_id_fn, "My_textfile") == "My_textfile"


def test_a_directory_in_the_name_is_dropped():
    """The name comes from the wiki, so it must not steer the download elsewhere."""
    result = build_target_fn(FilenameMode.name, OSW_ID_FN, "../../etc/passwd")

    assert result == "passwd.txt"


@pytest.mark.parametrize("name", [None, ""])
@pytest.mark.parametrize("mode", [FilenameMode.name, FilenameMode.name_and_osw_id])
def test_a_missing_name_falls_back_to_the_osw_id(mode, name):
    with pytest.warns(UserWarning, match="No name is stored"):
        assert build_target_fn(mode, OSW_ID_FN, name) == OSW_ID_FN


def test_an_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        build_target_fn("original", OSW_ID_FN, "My_textfile")
