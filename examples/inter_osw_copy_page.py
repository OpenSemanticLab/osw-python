"""This script provides the ability to copy a page from one OSW instance to another
OSW instance."""

from pathlib import Path

from typing_extensions import List, Optional, Union

from osw.auth import CredentialManager
from osw.core import OSW
from osw.model.static import OswBaseModel
from osw.utils import util
from osw.wtsite import SLOTS, WtPage, WtSite


class OswInstance(OswBaseModel):
    domain: str
    cred_fp: Union[str, Path]
    credentials_manager: Optional[CredentialManager]
    osw: Optional[OSW]
    wtsite: Optional[WtSite]

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, domain: str, cred_fp: Union[str, Path]):
        super().__init__(**{"domain": domain, "cred_fp": cred_fp})
        self.credentials_manager = CredentialManager(cred_filepath=cred_fp)
        self.osw = OSW(
            site=WtSite(
                WtSite.WtSiteConfig(iri=domain, cred_mngr=self.credentials_manager)
            )
        )
        self.wtsite = self.osw.site

    def get_page_content(self, full_page_titles: List[str]) -> dict:
        get_page_res: WtSite.GetPageResult = self.wtsite.get_page(
            WtSite.GetPageParam(titles=full_page_titles)
        )

        return_dict = {}
        for page in get_page_res.pages:
            title = page.title
            slot_contents = {}
            for slot in SLOTS:
                slot_content = page.get_slot_content(slot)
                if slot_content is not None:
                    slot_contents[slot] = slot_content
            return_dict[title] = slot_contents

        return return_dict

    def set_single_page_content(
        self,
        handover_dict: dict,
        comment: str,
        overwrite: bool = False,
    ):
        full_page_title: str = handover_dict["full_page_title"]
        content_dict: dict = handover_dict["content_dict"]
        wtpage = WtPage(
            wtSite=self.wtsite,
            title=full_page_title,
        )
        if wtpage.exists:
            if overwrite is False:
                print(
                    f"Page '{full_page_title}' already exists. It will not be updated."
                )
                return {full_page_title: False}
            changed_slots = []
            for slot in SLOTS:
                remote_content = wtpage.get_slot_content(slot)
                if remote_content != content_dict.get(slot, None):
                    changed_slots.append(slot)
            if len(changed_slots) == 0:
                print(
                    f"Page '{full_page_title}' already has the same content."
                    f" It will not be updated."
                )
                return {full_page_title: False}
            else:
                print(
                    f"Page '{full_page_title}' has different content in slots "
                    f"{changed_slots}. It will be updated."
                )
        for slot in content_dict.keys():
            wtpage.create_slot(
                slot_key=slot,
                content_model=SLOTS[slot]["content_model"],
            )
            wtpage.set_slot_content(
                slot_key=slot,
                content=content_dict[slot],
            )
        wtpage.edit(
            comment=comment,
        )
        print(f"Page updated: 'https://{self.domain}/wiki/{full_page_title}'")
        return {full_page_title: True}

    def set_page_contents(
        self, content_list: List[dict], comment: str, overwrite: bool = False
    ) -> list:
        result_list = util.parallelize(
            self.set_single_page_content,
            content_list,
            comment=comment,
            overwrite=overwrite,
            flush_at_end=True,
        )
        return result_list


def copy_pages_from(
    source_domain: str,
    to_target_domains: List[str],
    page_titles: List[str],
    cred_fp: Union[str, Path],
    comment: str = None,
    overwrite: bool = False,
):
    if comment is None:
        comment = f"[bot edit] Copied from {source_domain}"
    osw_source = OswInstance(
        domain=source_domain,
        cred_fp=cred_fp,
    )
    osw_targets = [
        OswInstance(
            domain=domain,
            cred_fp=cred_fp,
        )
        for domain in to_target_domains
    ]
    page_contents = osw_source.get_page_content(full_page_titles=page_titles)
    result = {}
    for osw_target in osw_targets:  # could also be parallelized!
        result[osw_target.domain] = osw_target.set_page_contents(
            content_list=[
                {
                    "full_page_title": full_page_title,
                    "content_dict": page_content,
                }
                for full_page_title, page_content in page_contents.items()
            ],
            comment=comment,
            overwrite=overwrite,
        )
    return result


if __name__ == "__main__":
    credentials_fp = Path(r"accounts.pwd.yaml")
    source = "onto-wiki.eu"
    targets = ["wiki-dev.open-semantic-lab.org"]
    titles = [
        "Item:OSW8dca6aaebe005c5faca05bac33264e4d",
        "Item:OSWaeffcee25ccb5dd8b42a434dc644d62c",
    ]
    # Implementation within this script
    use_this_script = False
    if use_this_script:
        copied_pages = copy_pages_from(
            source_domain=source,
            to_target_domains=targets,
            page_titles=titles,
            cred_fp=credentials_fp,
            overwrite=True,
        )
    # Implementation within wtsite
    use_wtsite = True
    if use_wtsite:
        osw_source = OswInstance(
            domain=source,
            cred_fp=credentials_fp,
        )
        osw_targets = [
            OswInstance(
                domain=target,
                cred_fp=credentials_fp,
            )
            for target in targets
        ]
        source_site = osw_source.wtsite
        target_sites = [osw_target.wtsite for osw_target in osw_targets]
        result = {}
        for target_site in target_sites:
            target = target_site._site.host
            copied_pages = target_site.copy_pages(
                WtSite.CopyPagesParam(
                    source_site=source_site,
                    existing_pages=titles,
                    overwrite=True,
                    parallel=False,
                )
            )
            result[target] = copied_pages
