import sys
import uuid as uuid_module
from pathlib import Path

import mwclient

import osw.wiki_tools as wt
from osw.data.import_utility import uuid_to_full_page_title
from osw.wtsite import WtPage, WtSite

# run with: tox -e test -- --wiki_domain domain --wiki_username user --wiki_password pass
# run locally with: tox -e test -- --wiki_domain None --wiki_username None --wiki_password None
# This will trigger the fallback option (and not the skip condition)


# Make non-package scripts available for import
cwd = Path(__file__).parent.absolute()
migration_import_dir = cwd.parents[1] / "scripts" / "migration"
sys.path.append(str(migration_import_dir))
# integration_import_dir = cwd.parents[1] / "tests" / "integration"
# sys.path.append(str(integration_import_dir))


def test_dependencies(wiki_domain: str, wiki_username: str, wiki_password: str):
    """This test makes sure that all dependencies are available. First the dependencies
    are fetched from the wiki if necessary, then the dependencies are checked.
    """
    import file_page_migration_dependencies as fpmd

    fpmd.main(wiki_domain, wiki_username, wiki_password)
    assert fpmd.check_dependencies()


def test_regex_pattern():
    from regex_pattern import REGEX_PATTERN_LIB

    for key, pattern in REGEX_PATTERN_LIB.items():
        assert pattern.test_pattern()
    pass


def test_file_page_migration(wiki_domain: str, wiki_username: str, wiki_password: str):
    from file_page_migration import (
        PWD_FILE_PATH,
        WikiFile,
        move_file_pages_and_redirect_references,
    )

    # For local testing without tox
    if wiki_domain is None or wiki_domain == "None":
        wtsite = WtSite.from_domain(
            domain="wiki-dev.open-semantic-lab.org",
            password_file=str(PWD_FILE_PATH),
        )
    # For testing with tox
    else:
        site = mwclient.Site(host=wiki_domain)
        site.login(username=wiki_username, password=wiki_password)
        wtsite = WtSite(WtSite.WtSiteLegacyConfig(site=site))

    # Path to the test file:
    bare_file_name = "test"
    file_name = (
        bare_file_name + ".svg"
    )  # OSW.get_osw_id(uuid_module.uuid4()) # + ".svg"
    # Using page
    using_page_fpt = uuid_to_full_page_title(uuid_module.uuid4())
    # File test page
    file_page_name = using_page_fpt.replace(":", "-") + "-" + file_name
    file_fpt = "File:" + file_page_name
    path_to_test_file = cwd / "test.svg"
    # Make sure the state is clean - delete the file if it exists, otherwise create it
    file_page = wtsite.get_WtPage(file_page_name)
    if file_page.exists:
        file_page.delete()
    with open(path_to_test_file, "r") as file:
        _ = wtsite._site.upload(
            file=file,
            filename=file_page_name,
            comment="File for testing the file_page_migration.py script. "
            "Can be deleted.",
            description="Test file",
            ignore=True,
        )
    # Make sure the state is clean - delete the using page if it exists, otherwise
    #  create it
    using_page = WtPage(wtSite=wtsite, title=using_page_fpt)
    if using_page.exists:
        using_page.delete()
    using_page.set_slot_content(
        slot_key="main",
        content="{{Template:Editor/SvgEdit|file_name="
        + bare_file_name
        + "| page_name="
        + using_page_fpt
        + "}}",
    )
    using_page.edit(comment="Test")
    print("Using page created: " + using_page_fpt)
    ###############################################
    # Test the migration (serial and parallel) # todo: test parallel
    result = move_file_pages_and_redirect_references(
        file_pages=[file_fpt], wtsite_obj=wtsite, parallel=False
    )
    ###############################################
    new_full_page_name = result[0]
    new_file_page = wtsite.get_WtPage(new_full_page_name)
    # Assert that the result is as expected
    exception = None
    try:
        # # Make sure the changes are propagated / Caches are invalidated
        # new_file_page.purge()
        # # Get the new file page after purging
        # new_file_page = wtsite.get_WtPage(new_full_page_name)
        print(f"Fetching jsondata of {new_full_page_name}")
        assert new_file_page.exists
        assert new_file_page.is_file_page
        jsondata = new_file_page.get_slot_content("jsondata")
        if jsondata is None:
            raise ValueError(
                "jsondata is None - meta data was not written to the file " "page!"
            )
        assert jsondata["type"] == WikiFile.__fields__["type"].default
        modified_using_page = wtsite.get_WtPage(using_page_fpt)
        main_slot_content = modified_using_page.get_slot_content("main")
        parsed_content = wt.create_flat_content_structure_from_wikitext(
            main_slot_content
        )
        content_dict = parsed_content[0]
        assert bare_file_name in content_dict["Template:Editor/SvgEdit"]["file_name"]
        assert "uuid" in list(content_dict.values())[0].keys()
    except AssertionError as e:
        # Assertion Error for now
        exception = e
    finally:
        # Make sure the state is clean - delete the created pages
        # Delete the using page
        using_page.delete(comment="Test finished")
        # Delete the file page
        new_file_page.delete(comment="Test finished")
        # Now raise the exception if there was one
        if exception is not None:
            raise exception


# Dummy call to avoid warning
# helper.foobar()
if __name__ == "__main__":
    test_file_page_migration()
