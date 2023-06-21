import sys
import uuid as uuid_module
from pathlib import Path

# Make sure model dependencies are available before importing osw.model.entity
import file_page_migration_dependencies as fpmd
import mwclient

import osw.model.entity as model
import osw.wiki_tools as wt
from osw.core import OSW
from osw.data.import_utility import uuid_to_full_page_title
from osw.wtsite import WtSite

# Make non-package scripts available for import
cwd = Path.cwd()
import_dir = cwd.parents[0] / "scripts" / "migration"
sys.path.append(str(import_dir))


# run with:
#  tox -e test -- --wiki_domain domain --wiki_username user --wiki_password pass


def test_dependencies(
    wiki_domain: str = None, wiki_username: str = None, wiki_password: str = None
):
    """This test makes sure that all dependencies are available. First the dependencies
    are fetched from the wiki if necessary, then the dependencies are checked.
    """
    fpmd.main(wiki_domain, wiki_username, wiki_password)
    # import osw.model.entity as model
    assert fpmd.check_dependencies()


def test_regex_pattern():
    from file_page_migration import REGEX_PATTERN_LIB

    for key, pattern in REGEX_PATTERN_LIB.items():
        assert pattern.test_pattern()
    pass


def test_file_page_migration(
    wiki_domain: str = None, wiki_username: str = None, wiki_password: str = None
):
    from file_page_migration import (
        PWD_FILE_PATH,
        WikiFile,
        make_the_move_and_redirect_references,
    )

    # For local testing without tox
    if wiki_domain is None:
        wtsite = WtSite.from_domain(
            domain="wiki-dev.open-semantic-lab.org",
            password_file=str(PWD_FILE_PATH),
        )
    # For testing with tox
    else:
        site = mwclient.Site(host=wiki_domain)
        site.login(username=wiki_username, password=wiki_password)
        # wtsite = WtSite(WtSite.WtSiteLegacyConfig(site=site))
        wtsite = WtSite(site=site)

    # Path to the test file:
    file_name_without_suffix = (
        f"ABC{str(uuid_module.uuid4()).replace('-', '')}" f"-file_page_migration_test"
    )
    suffix = ".svg"
    file_name = file_name_without_suffix + suffix
    page_name = f"File:{file_name}"
    path_to_test_file = cwd / file_name
    # Make sure the state is clean - delete the file if it exists, otherwise create it
    if path_to_test_file.exists():
        path_to_test_file.unlink()
    # Create a random image at the specified location
    fpmd.random_image(file_path=path_to_test_file)
    # Create a WtSite object

    osw = OSW(site=wtsite)
    # Make sure the state is clean - delete the file if it exists, otherwise create it
    file_page = wtsite.get_WtPage(page_name)
    if file_page.exists:
        file_page.delete()
    with open(path_to_test_file, "rb") as file:
        _ = wtsite._site.upload(
            file=file,
            filename=file_name,
            comment="File for testing the file_page_migration.py script. "
            "Can be deleted.",
        )
    # Create a using page
    using_page_uuid = uuid_module.uuid4()
    rnd_item = model.Item(
        uuid=using_page_uuid,
        label=[model.Label(text="Delete me")],
    )
    osw.store_entity(OSW.StoreEntityParam(entities=rnd_item, namespace="Item"))
    # osw_id = osw.get_osw_id(using_page_uuid)
    using_page_name = uuid_to_full_page_title(using_page_uuid)
    using_page = wtsite.get_WtPage(using_page_name)
    using_page.set_slot_content(
        slot_key="main",
        content="""
        {{Template:Editor/SvgEdit
        |file_name=$file_name$|type=$suffix$}}
        """.replace(
            "$file_name$", file_name_without_suffix
        ).replace(
            "$suffix$", suffix
        ),
    )
    using_page.edit()
    ###############################################
    # Test the migration (serial and parallel) # todo: parallel
    result = make_the_move_and_redirect_references(
        file_pages=[page_name], wtsite_obj=wtsite, parallel=False
    )
    ###############################################
    # Assert that the result is as expected
    new_full_page_name = result[0]
    new_file_page = wtsite.get_WtPage(new_full_page_name)
    assert new_file_page.exists
    assert new_file_page.is_file_page
    jsondata = new_file_page.get_slot_content("jsondata")
    if jsondata is None:
        raise ValueError(
            "jsondata is None - meta data was not written to the file " "page!"
        )
    assert jsondata["type"] == WikiFile.__fields__["type"].default
    modified_using_page = wtsite.get_WtPage(using_page_name)
    main_slot_content = modified_using_page.get_slot_content("main")
    parsed_content = wt.create_flat_content_structure_from_wikitext(main_slot_content)
    content_dict = parsed_content[0]
    import pprint

    pprint.pprint(parsed_content)
    assert content_dict["Template:Editor/SvgEdit"]["file_name"] == [
        file_name_without_suffix
    ]
    assert "uuid" in list(content_dict.values())[0].keys()

    # Delete the using page
    # Delete the file page
    """
    file_page_moved = wtsite.get_WtPage(page_name_after_move)
    if file_page_moved.exists:
        file_page_moved.delete()
    # finally delete the file
    path_to_test_file.unlink()
    """
    # todo:
    #  reference should be updated
    #  file page should be a WikiFile


# Dummy call to avoid warning
# helper.foobar()
if __name__ == "__main__":
    test_file_page_migration()
