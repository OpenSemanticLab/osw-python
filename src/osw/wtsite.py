# extents mwclient.site

import json
import os
import shutil
from datetime import datetime
from pprint import pprint
from typing import List, Optional

import mwclient
from jsonpath_ng.ext import parse
from pydantic import BaseModel

import osw.model.page_package as package
import osw.wiki_tools as wt
from osw.model.entity import _basemodel_decorator


class WtSite:
    def __init__(self, site: mwclient.Site = None):
        if site:
            self._site = site
        else:
            raise ValueError("Parameter 'site' is None")
        self._page_cache = {}
        self._cache_enabled = False

    @classmethod
    def from_domain(cls, domain: str = None, password_file: str = None):
        site = wt.create_site_object(domain, password_file)
        return cls(site)

    def get_WtPage(self, title: str = None):
        if self._cache_enabled and title in self._page_cache:
            return self._page_cache[title]
        else:
            wtpage = WtPage(self, title)
            if self._cache_enabled:
                self._page_cache[title] = wtpage
        return wtpage

    def enable_cache(self):
        self._cache_enabled = True

    def disable_cache(self):
        self._cache_enabled = False

    def get_cache_enabled(self):
        return self._cache_enabled

    def clear_cache(self):
        del self._page_cache
        self._page_cache = {}

    def prefix_search(self, text):
        return wt.prefix_search(self._site, text)

    def semantic_search(self, query):
        return wt.semantic_search(self._site, query)

    def modify_search_results(
        self,
        mode: str,
        query: str,
        modify_page,
        limit=None,
        comment=None,
        log=False,
        dryrun=False,
    ):
        titles = []
        if mode == "prefix":
            titles = wt.prefix_search(self._site, query)
        elif mode == "semantic":
            titles = wt.semantic_search(self._site, query)
        if limit:
            titles = titles[0:limit]
        if log:
            print(f"Found: {titles}")
        for title in titles:
            wtpage = self.get_WtPage(title)
            modify_page(wtpage)
            if log:
                print(f"\n======= {title} =======")
                print(wtpage._content)
                for slot in wtpage._slots:
                    content = wtpage.get_slot_content(slot)
                    # if isinstance(content, dict): content = json.dumps(content)
                    print(f"   ==== {title}:{slot} ====   ")
                    pprint(content)
                    print("\n")
            if not dryrun:
                wtpage.edit(comment)

    class PagePackageConfig(BaseModel):
        name: str
        target_path: str
        titles: List[str]
        # replace: Optional[bool] = False
        bundle: package.PagePackageBundle

    def create_page_package(self, config: PagePackageConfig):
        try:
            shutil.rmtree(os.path.dirname(config.target_path))
        except OSError as e:
            print("Error: %s - %s." % (e.filename, e.strerror))
        dump_config = WtPage.PageDumpConfig(
            target_dir=os.path.dirname(config.target_path)
        )
        bundle = config.bundle
        if config.name not in bundle.packages:
            print(f"Error: package {config.name} does not exist in bundle")
            return
        if not bundle.packages[config.name].pages:
            bundle.packages[config.name].pages = []
        for title in config.titles:
            page = self.get_WtPage(title)
            bundle.packages[config.name].pages.append(page.dump(dump_config))

        content = bundle.json(exclude_none=True, indent=4)
        file_name = f"{config.target_path}"
        with open(file_name, "w") as f:
            f.write(content)


class WtPage:
    def __init__(self, wtSite: WtSite = None, title: str = None):
        self.wtSite = wtSite
        self.title = title

        self._page = wtSite._site.pages[self.title]
        self.exists = self._page.exists
        self._original_content = ""
        self._content = ""
        self.changed = False
        self._dict = []
        self._slots = {"main": ""}
        self._slots_changed = {"main": False}
        self._content_model = {"main": "wikitext"}

        if self.exists:
            self._original_content = self._page.text()
            self._content = self._original_content
            self._dict = wt.create_flat_content_structure_from_wikitext(
                self._content, array_mode="only_multiple"
            )
            # multi content revisions
            rev = wtSite._site.api(
                "query",
                prop="revisions",
                titles=title,
                rvprop="ids|timestamp|flags|comment|user|content|contentmodel|roles|slotsize",
                rvslots="*",
                rvlimit="1",
                format="json",
            )
            for page_id in rev["query"]["pages"]:
                page = rev["query"]["pages"][page_id]
                if page["title"] == title:
                    for revision in page["revisions"]:
                        self._current_revision = revision
                        for slot_key in revision["slots"]:
                            self._slots[slot_key] = revision["slots"][slot_key]["*"]
                            self._content_model[slot_key] = revision["slots"][slot_key][
                                "contentmodel"
                            ]
                            self._slots_changed[slot_key] = False
                            if self._content_model[slot_key] == "json":
                                self._slots[slot_key] = json.loads(
                                    self._slots[slot_key]
                                )

    def create_slot(self, slot_key, content_model):
        self._slots[slot_key] = None
        self._slots_changed[slot_key] = False
        self._content_model[slot_key] = content_model

    def get_content(self):
        return self._content

    def get_slot_content(self, slot_key):
        if slot_key not in self._slots:
            return None
        return self._slots[slot_key]

    def get_slot_content_model(self, slot_key):
        if slot_key not in self._slots:
            return None
        return self._content_model[slot_key]

    def set_content(self, content):
        self._content = content
        self.changed = True

    def set_slot_content(self, slot_key, content):
        if slot_key not in self._slots:
            content_model = "json"
            if type(content) == str:
                content_model = "wikitext"
            self.create_slot(slot_key, content_model)
        if content != self._slots[slot_key]:
            self._slots_changed[slot_key] = True
        self._slots[slot_key] = content

    def get_url(self) -> str:
        return "https://" + self.wtSite._site.host + "/wiki/" + self.title

    def append_template(self, template_name: str = None, template_params: dict = None):
        self._dict.append({template_name: template_params})
        return self

    def append_text(self, text):
        self._dict.append(text)
        return self

    def get_value(self, jsonpath):
        jsonpath_expr = parse(jsonpath)
        res = []
        d = dict(
            zip(range(len(self._dict)), self._dict)
        )  # convert list to dict with index
        for match in jsonpath_expr.find(d):
            res.append(match.value)
        return res

    def update_dict(combined: dict, update: dict) -> None:
        for k, v in update.items():
            if isinstance(v, dict):
                WtPage.combine_into(v, combined.setdefault(k, {}))
            else:
                combined[k] = v

    def set_value(self, jsonpath_match, value, replace=False):
        jsonpath_expr = parse(jsonpath_match)
        d = dict(
            zip(range(len(self._dict)), self._dict)
        )  # convert list to dict with index
        # if create: jsonpath_expr.update_or_create(d, value)
        # else: jsonpath_expr.update(d, value)
        matches = jsonpath_expr.find(d)
        for match in matches:
            print(match.full_path)
            # pprint(value)
            if not replace:
                WtPage.update_dict(match.value, value)
                value = match.value
            # pprint(value)
            match.full_path.update_or_create(d, value)
        self._dict = list(d.values())  # convert dict with index to list
        return self

    def update_content(self):
        self._content = wt.get_wikitext_from_flat_content_structure(self._dict)
        self.changed = self._original_content != self._content
        return self

    def edit(self, comment: str = None):
        if not comment:
            comment = "[bot] update of page content"
        if self.changed:
            self._page.edit(self._content, comment)
        for slot_key in self._slots:
            if self._slots_changed[slot_key]:
                content = self._slots[slot_key]
                if self._content_model[slot_key] == "json":
                    content = json.dumps(content)
                self.wtSite._site.api(
                    "editslot",
                    token=self.wtSite._site.get_token("csrf"),
                    title=self.title,
                    slot=slot_key,
                    text=content,
                    summary=comment,
                )

    def delete(self, comment: str = None):
        self._page.delete(comment)

    def move(self, new_title: str, comment: str = None, redirect=True):
        if new_title != self.title:
            print(f"move '{self.title}' to '{new_title}'")
            self._page.move(
                new_title=new_title, reason=comment, no_redirect=not redirect
            )
            self.title = new_title

    def get_last_changed_time(self):
        return datetime.fromisoformat(
            self._current_revision["timestamp"].replace("Z", "+00:00")
        )

    @_basemodel_decorator
    class PageDumpConfig(BaseModel):
        target_dir: str
        namespace_as_folder: Optional[bool] = True

        class Config:
            arbitrary_types_allowed = True  # neccessary to allow e.g. np.array as type

    def dump(self, config: PageDumpConfig):
        page_name = self.title.split(":")[-1]
        if ":" in self.title:
            namespace = self.title.split(":")[0]
        else:
            namespace = "Main"
        namespace_const = "NS_" + namespace.upper()
        # namespace_id = self._page.namespace

        package_page = package.PagePackagePage(
            name=page_name, namespace=namespace_const, slots={}
        )

        dir = config.target_dir
        path_prefix = ""
        if config.namespace_as_folder:
            dir = os.path.join(dir, namespace)
            path_prefix = namespace + "/"
        # if not os.path.exists(dir):
        #    os.makedirs(dir)
        for slot_key in self._slots:
            content = self.get_slot_content(slot_key)
            if isinstance(content, dict):
                content = json.dumps(content, indent=4)
            content_type = self.get_slot_content_model(slot_key)
            if content_type == "Scribunto":
                content_type = "lua"
            file_name = f"{page_name}.slot_{slot_key}.{content_type}"
            file_path = os.path.join(dir, *file_name.split("/"))  # handle subpages
            if not os.path.exists(os.path.dirname(file_path)):
                os.makedirs(os.path.dirname(file_path))
            with open(os.path.join(file_path), "w") as f:
                f.write(content)
            if slot_key == "main":
                package_page.urlPath = path_prefix + file_name
            else:
                package_page.slots[slot_key] = package.PagePackagePageSlot(
                    urlPath=path_prefix + file_name
                )

        return package_page
