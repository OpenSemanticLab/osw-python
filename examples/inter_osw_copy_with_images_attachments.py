"""Copy pages from one OSW instance to another with optional dependency resolution
for images/attachments, Category pages, and Property pages.

Two-phase approach:
  1. collect_pages() — fetch pages + dependencies, dump to local page package
  2. push_pages()    — read local package, upload to target instance
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

from osw.auth import CredentialManager
from osw.express import OswExpress
from osw.model.page_package import (
    NAMESPACE_CONST_TO_NAMESPACE_MAPPING,
    PagePackage,
    PagePackageBundle,
    PagePackageConfig,
)
from osw.params import CreatePagePackageParam, PageDumpConfig
from osw.wtsite import WtPage, WtSite

log = logging.getLogger(__name__)


class OswInstance:
    """Wrapper for connecting to an OSW instance."""

    def __init__(self, domain: str, cred_filepath: Union[str, Path]):
        self.domain = domain
        self.credentials_manager = CredentialManager(cred_filepath=cred_filepath)
        self.osw = OswExpress(domain=domain, cred_mngr=self.credentials_manager)
        self.wtsite: WtSite = self.osw.site


def extract_file_refs(page: WtPage) -> List[str]:
    """Extract File: page references from all slots of a page."""
    return page.find_file_page_refs_in_slots()


def extract_category_deps(page: WtPage) -> List[str]:
    """Extract direct category dependencies from jsondata['type']."""
    jsondata = page.get_slot_content("jsondata")
    if not isinstance(jsondata, dict):
        return []
    return [
        t
        for t in jsondata.get("type", [])
        if isinstance(t, str) and t.startswith("Category:")
    ]


def extract_category_parents(page: WtPage) -> List[str]:
    """Extract parent category references from jsondata['subclass_of']
    and jsonschema @context / allOf parent references."""
    parents = set()

    jsondata = page.get_slot_content("jsondata")
    if isinstance(jsondata, dict):
        for p in jsondata.get("subclass_of", []):
            if isinstance(p, str) and p.startswith("Category:"):
                parents.add(p)

    schema = page.get_slot_content("jsonschema")
    if isinstance(schema, dict):
        context = schema.get("@context", [])
        if isinstance(context, list):
            for entry in context:
                if isinstance(entry, str) and "/wiki/Category:" in entry:
                    title = entry.split("/wiki/")[-1].split("?")[0]
                    parents.add(title)

        for ref_obj in schema.get("allOf", []):
            if isinstance(ref_obj, dict) and "$ref" in ref_obj:
                ref_val = ref_obj["$ref"]
                if "/wiki/Category:" in ref_val:
                    title = ref_val.split("/wiki/")[-1].split("?")[0]
                    parents.add(title)

    return list(parents)


def extract_property_deps(page: WtPage) -> List[str]:
    """Extract Property: page references from jsonschema @context."""
    properties: Set[str] = set()
    schema = page.get_slot_content("jsonschema")
    if not isinstance(schema, dict):
        return []

    context = schema.get("@context", [])
    entries = context if isinstance(context, list) else [context]

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for _key, value in entry.items():
            if isinstance(value, dict):
                id_val = value.get("@id", "")
                if id_val.startswith("Property:"):
                    properties.add(id_val)
            elif isinstance(value, str) and value.startswith("Property:"):
                properties.add(value)

    return list(properties)


def check_existing_on_target(target: OswInstance, titles: List[str]) -> Set[str]:
    """Check which page titles already exist on the target instance."""
    existing = set()
    for title in titles:
        try:
            if target.wtsite.mw_site.pages[title].exists:
                existing.add(title)
        except Exception:
            pass
    return existing


def download_file_binaries(
    source: OswInstance, file_titles: List[str], package_dir: Path
) -> None:
    """Re-download file binaries using OswExpress.download_file which handles
    authentication properly (the raw mwclient download in WtPage.dump may
    return HTML instead of binary data)."""
    for title in file_titles:
        page_name = title.split(":", 1)[1]
        binary_path = package_dir / "File" / page_name
        binary_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            source.osw.download_file(
                url_or_title=title,
                target_fp=binary_path,
                overwrite=True,
            )
            log.info(f"Downloaded binary for '{title}'.")
        except Exception as e:
            log.error(f"Failed to download binary for '{title}': {e}")


def upload_file_binary(
    target: OswInstance, title: str, binary_path: Path
) -> None:
    """Upload a binary file to the target instance.

    Uses mw_site.upload() directly instead of OswExpress.upload_file() because
    the express method creates a new WikiFile entity with a random UUID and then
    calls store_entity, which fails with a UUID mismatch when the page title
    implies a different UUID.  The correct metadata is written separately by
    page.edit() in push_pages(), so only the raw binary upload is needed here.
    """
    page_name = title.split(":", 1)[1]
    with open(binary_path, "rb") as fh:
        target.wtsite.mw_site.upload(
            file=fh,
            filename=page_name,
            ignore=True,
        )


def resolve_categories(
    source: OswInstance,
    target: OswInstance,
    seed_titles: List[str],
    max_depth: int = 10,
) -> List[str]:
    """Resolve category hierarchy via BFS.

    Returns categories that need to be copied (not already present on
    target), ordered parents-before-children.
    """
    to_collect: List[str] = []
    visited: Set[str] = set()
    queue: List[tuple] = [(title, 0) for title in seed_titles]

    while queue:
        title, depth = queue.pop(0)
        if title in visited or depth > max_depth:
            continue
        visited.add(title)

        try:
            if target.wtsite.mw_site.pages[title].exists:
                log.info(f"Category '{title}' already exists on target, skipping.")
                continue
        except Exception:
            pass

        try:
            result = source.wtsite.get_page(
                WtSite.GetPageParam(titles=[title])
            )
            if not result.pages:
                log.warning(f"Category '{title}' not found on source.")
                continue
            source_page = result.pages[0]
        except Exception as e:
            log.warning(f"Failed to fetch category '{title}' from source: {e}")
            continue

        to_collect.append(title)

        for parent in extract_category_parents(source_page):
            if parent not in visited:
                queue.append((parent, depth + 1))

    # Reverse so parents come before children
    to_collect.reverse()
    return to_collect


def collect_pages(
    source: OswInstance,
    target: OswInstance,
    titles: List[str],
    output_dir: Path,
    include_files: bool = False,
    include_categories: bool = False,
    include_properties: bool = False,
    category_max_depth: int = 10,
    package_name: str = "copy_package",
) -> Dict:
    """Phase 1: Fetch pages and their dependencies from the source, dump to a
    local page package.

    Parameters
    ----------
    source
        The source OSW instance to fetch from.
    target
        The target OSW instance (used to check which dependencies already exist).
    titles
        Full page titles to copy (e.g. ``["Item:OSW..."]``).
    output_dir
        Local directory for the page package.
    include_files
        Resolve and include File: page dependencies (images, attachments).
    include_categories
        Resolve and include Category page dependencies (recursive, skipping
        those already on target).
    include_properties
        Resolve and include Property page dependencies from @context (skipping
        those already on target).
    category_max_depth
        Maximum recursion depth for category parent resolution.
    package_name
        Name for the page package manifest.

    Returns
    -------
    dict
        Summary of what was collected, keyed by dependency type.
    """
    log.info(f"Fetching {len(titles)} primary pages from {source.domain}...")
    primary_result = source.wtsite.get_page(
        WtSite.GetPageParam(titles=titles)
    )
    primary_pages = primary_result.pages
    log.info(f"Fetched {len(primary_pages)} primary pages.")

    category_titles: List[str] = []
    property_titles: List[str] = []
    file_titles: List[str] = []
    all_pages = list(primary_pages)

    # --- Category dependencies (recursive, with target check) ---
    if include_categories:
        seed_categories: Set[str] = set()
        for page in primary_pages:
            seed_categories.update(extract_category_deps(page))
        log.info(
            f"Found {len(seed_categories)} direct category dependencies, "
            "resolving hierarchy..."
        )
        category_titles = resolve_categories(
            source=source,
            target=target,
            seed_titles=list(seed_categories),
            max_depth=category_max_depth,
        )
        if category_titles:
            cat_result = source.wtsite.get_page(
                WtSite.GetPageParam(titles=category_titles)
            )
            all_pages.extend(cat_result.pages)
        log.info(f"Resolved to {len(category_titles)} categories to copy.")

    # --- Property dependencies (from primary pages AND collected categories) ---
    if include_properties:
        all_property_refs: Set[str] = set()
        for page in all_pages:
            all_property_refs.update(extract_property_deps(page))

        if all_property_refs:
            existing_props = check_existing_on_target(
                target, list(all_property_refs)
            )
            property_titles = [
                p for p in all_property_refs if p not in existing_props
            ]
            skipped = len(all_property_refs) - len(property_titles)
            if skipped:
                log.info(f"Skipped {skipped} properties already on target.")
        log.info(f"Found {len(property_titles)} property dependencies to copy.")

    # --- File dependencies (from ALL collected pages, not just primary) ---
    # Scanned after categories are collected because category pages can also
    # reference File: pages (e.g. icon images) that would otherwise be missed.
    if include_files:
        file_refs: Set[str] = set()
        for page in all_pages:
            file_refs.update(extract_file_refs(page))
        file_titles = list(file_refs)
        log.info(f"Found {len(file_titles)} file dependencies.")

    # --- Combine and deduplicate (dependency order) ---
    all_titles = list(
        dict.fromkeys(property_titles + category_titles + file_titles + titles)
    )
    log.info(f"Total pages to package: {len(all_titles)}")

    # --- Create local page package ---
    source.wtsite.create_page_package(
        CreatePagePackageParam(
            config=PagePackageConfig(
                name=package_name,
                config_path=output_dir / "packages.json",
                content_path=output_dir,
                titles=all_titles,
                include_files=False,
                bundle=PagePackageBundle(
                    packages={
                        package_name: PagePackage(
                            globalID=package_name,
                            description=f"Copy package from {source.domain}",
                            version="0.1.0",
                            baseURL=f"https://{source.domain}",
                        )
                    }
                ),
            ),
            dump_config=PageDumpConfig(target_dir=output_dir),
        )
    )

    # WtPage.dump() uses mwclient's file.download() which doesn't carry the
    # authenticated session cookie, so the wiki returns an HTML login page
    # instead of the actual binary.  Re-download via OswExpress.download_file()
    # which uses api.php?action=download with the authenticated connection.
    if file_titles:
        log.info("Re-downloading file binaries via WikiFileController...")
        download_file_binaries(source, file_titles, output_dir)

    summary = {
        "primary_pages": titles,
        "file_pages": file_titles,
        "category_pages": category_titles,
        "property_pages": property_titles,
        "total": len(all_titles),
        "output_dir": str(output_dir),
    }
    log.info(f"Package created at {output_dir}")
    return summary


def push_pages(
    target: OswInstance,
    package_dir: Path,
    comment: Optional[str] = None,
    overwrite: bool = False,
) -> Dict:
    """Phase 2: Read a local page package and upload to the target instance.

    Uploads in dependency order: Properties -> Categories -> Files -> Primary pages.
    For File: pages, also uploads the binary file content.

    Parameters
    ----------
    target
        The target OSW instance to upload to.
    package_dir
        Path to the local page package directory.
    comment
        Edit comment for the page history.
    overwrite
        If False, skip pages that already exist on the target.

    Returns
    -------
    dict
        Upload results with lists of uploaded, skipped, and failed titles.
    """
    if comment is None:
        comment = "[bot edit] Copied from page package"

    result = target.wtsite.read_page_package(
        WtSite.ReadPagePackageParam(
            storage_path=package_dir,
            offline=True,
        )
    )
    pages = result.pages

    # Workaround: WtSite.read_page_package() iterates only over page["slots"]
    # in packages.json, but the main slot's path is stored one level up at
    # page["urlPath"] (not inside page["slots"]).  So the main slot wikitext
    # is never loaded for pages that have other slots (jsondata, header, …).
    # We parse packages.json ourselves to reconstruct the page title → main
    # slot file mapping and load the content manually.
    packages_json_path = package_dir / "packages.json"
    if packages_json_path.exists():
        with open(packages_json_path, encoding="utf-8") as f:
            packages_json = json.load(f)
        main_slot_map: Dict[str, str] = {}
        for _pkg_name, pkg_dict in packages_json["packages"].items():
            for page_info in pkg_dict["pages"]:
                ns_name = NAMESPACE_CONST_TO_NAMESPACE_MAPPING.get(
                    page_info["namespace"], "Main"
                )
                if ns_name == "Main":
                    full_title = page_info["name"]
                else:
                    full_title = f"{ns_name}:{page_info['name']}"
                main_slot_map[full_title] = page_info.get("urlPath", "")

        for page in pages:
            url_path = main_slot_map.get(page.title, "")
            if not url_path:
                continue
            main_file = package_dir / url_path
            if main_file.exists():
                with open(main_file, encoding="utf-8") as f:
                    content = f.read()
                if content:
                    page.set_slot_content("main", content)

    # Sort pages by type for dependency-ordered upload
    property_pages = []
    category_pages = []
    file_pages = []
    primary_pages = []

    for page in pages:
        title = page.title
        if title.startswith("Property:"):
            property_pages.append(page)
        elif title.startswith("Category:"):
            category_pages.append(page)
        elif title.startswith("File:"):
            file_pages.append(page)
        else:
            primary_pages.append(page)

    ordered_pages = property_pages + category_pages + file_pages + primary_pages

    results: Dict[str, list] = {"uploaded": [], "skipped": [], "failed": []}

    for page in ordered_pages:
        title = page.title

        if not overwrite:
            try:
                if target.wtsite.mw_site.pages[title].exists:
                    log.info(f"Skipping '{title}' — already exists on target.")
                    results["skipped"].append(title)
                    continue
            except Exception:
                pass

        is_file_page = title.startswith("File:")
        page_name = title.split(":", 1)[1] if is_file_page else None
        binary_path = package_dir / "File" / page_name if is_file_page else None

        # For File: pages, upload binary first via OswExpress (matches wiki.py pattern)
        if is_file_page and binary_path and binary_path.exists():
            try:
                upload_file_binary(target, title, binary_path)
                log.info(f"Uploaded binary file for '{title}'.")
            except Exception as e:
                log.error(f"Failed to upload binary for '{title}': {e}")
                results["failed"].append(title)
                continue
        elif is_file_page:
            log.warning(f"Binary file not found at {binary_path}")

        # Upload slot content
        try:
            page.edit(comment=comment)
            log.info(f"Uploaded slots for '{title}'.")
            results["uploaded"].append(title)
        except Exception as e:
            log.error(f"Failed to upload '{title}': {e}")
            results["failed"].append(title)

    log.info(
        f"Push complete: {len(results['uploaded'])} uploaded, "
        f"{len(results['skipped'])} skipped, {len(results['failed'])} failed."
    )
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    cred_filepath = Path("accounts.pwd.yaml")
    source_domain = "arkeve.isc.fraunhofer.de"
    target_domain = "wiki-dev.open-semantic-lab.org"

    source_inst = OswInstance(domain=source_domain, cred_filepath=cred_filepath)
    target_inst = OswInstance(domain=target_domain, cred_filepath=cred_filepath)

    titles_to_copy = [
        #"Category:OSW3e5fdb3c3e614f5cbfb08899b2935bcd",  # Automated Experimental Setup
        "Item:OSW2f753c2a187d403994a18ef1ed4cea68", # delete_me_test_for_copying
        #"Category:OSW0b5e4975ee904456b4630c41b418fab3" # Delete me category
    ]
    output_dir = Path("osw_copy_package")

    # Phase 1: Collect
    summary = collect_pages(
        source=source_inst,
        target=target_inst,
        titles=titles_to_copy,
        output_dir=output_dir,
        include_files=True,
        include_categories=True,
        include_properties=True,
        category_max_depth=10,
    )
    print("Collection summary:")
    print(json.dumps(summary, indent=2))

    # Inspection point
    input(
        f"\nInspect the package at '{output_dir}'."
        " Press Enter to push, or Ctrl+C to abort..."
    )

    # Phase 2: Push
    push_result = push_pages(
        target=target_inst,
        package_dir=output_dir,
        comment=f"[bot edit] Copied from {source_domain}",
        overwrite=False,
    )
    print("\nUpload results:")
    print(json.dumps(push_result, indent=2))
