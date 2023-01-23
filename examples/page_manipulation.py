import json
import os
from datetime import datetime
from pprint import pprint

import osw.wiki_tools as wt
from osw.wtsite import WtPage, WtSite

pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)


def basic_text_manipulation():
    wikitext_org = """{{OslTemplate:LIMS/Device/Type
    |timestamp=2022-10-10T00:00:00.000Z
    |creator=C1;C2
    |display_name=Test Term
    |label=Device Test Type with Term
    |label_lang_code=en
    |description=Some description
    with line break
    |category=Category:OSWa444b0eeb79140d58a836a7fc6fc940a
    |relations={{OslTemplate:KB/Relation
    |property=IsRelatedTo
    |value=Term:OSW6b663c61c12d42e8be37d735dd2a869c
    }}SomeText{{OslTemplate:KB/Relation
    |property=IsRelatedTo
    |value=Term:OSW6b663c61c12d42e8be37d735dd2a869c
    }}
    }}
    =Details=
    some text

    {{Some/Template
    |p1=v1
    }}

    <br />
    {{OslTemplate:LIMS/Device/Type/Footer
    }}"""

    content_dict_1 = wt.create_flat_content_structure_from_wikitext(wikitext_org)
    pprint(content_dict_1)

    wikitext_2 = wt.get_wikitext_from_flat_content_structure(content_dict_1)
    print(wikitext_2)
    if wikitext_2 == wikitext_org:
        print("wikitext_2 == wikitext_org")
    else:
        print("wikitext_2 != wikitext_org")

    content_dict_3 = wt.create_flat_content_structure_from_wikitext(wikitext_2)
    pprint(content_dict_3)
    wikitext_3 = wt.get_wikitext_from_flat_content_structure(content_dict_3)
    print(wikitext_3)
    if wikitext_3 == wikitext_2:
        print("wikitext_3 == wikitext_2")
    else:
        print("wikitext_3 != wikitext_2")

    content_dict_3[0]["OslTemplate:LIMS/Device/Type"]["display_name"] = "NEW VALUE"
    print(wt.get_wikitext_from_flat_content_structure(content_dict_3))


def mass_page_edit():
    wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)
    # wtpage = wtsite.get_WtPage("LabNote:220601-sist-0001-ni")
    # wtpage = wtsite.get_WtPage("testesfesefsef")
    # wtpage.append_template("TestTemplate", {"p1": "v1"})
    # wtpage.append_text("Some text",)
    # wtpage.append_template("TestTemplate", {"p1": "v2"})

    # pprint(wtpage._dict)

    # res = wtpage.get_value("*.TestTemplate.p1")
    # pprint(res)
    # d = wtpage.set_value("*.TestTemplate.p1", "v3")

    # local_id = wtpage.title.split(":")[1]
    # wtpage.set_value("*.'OslTemplate:ELN/Entry/Header'", {"local_id" : [local_id]})

    # wtpage.update_content()
    # pprint(wtpage._dict)
    # wtpage.edit()
    # print(wtpage.changed)

    wtsite.modify_search_results(
        "semantic",
        "[[Category:labNote]]",
        lambda wtpage:
        # print("Lambda")#wtpage.title)
        wtpage.set_value(
            "*.'OslTemplate:ELN/Entry/Header'", {"id": [wtpage.title.split(":")[1]]}
        ).update_content(),
        limit=1,
        comment="[bot] set id from title",
        log=True,
        dryrun=True,
    )


def schema_renaming():
    wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)

    def modify(wtpage: WtPage):
        wtpage.content_replace("_osl_template", "osl_template")
        wtpage.content_replace("_osl_footer", "osl_footer")

    wtsite.modify_search_results(
        "prefix",
        "JsonSchema:",
        modify,
        limit=20,
        comment="rename keywords _osl* to osl*",
        log=True,
        dryrun=False,
    )


def slot_default_values():
    wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)

    def modify(wtpage: WtPage):
        edit = True
        # print(wtpage.get_last_changed_time())
        # if wtpage.get_last_changed_time() > datetime.fromisoformat('2023-01-15T12:00:00+00:00'):
        #    print("new")
        # else:
        #    print("old")
        #    edit = False
        if edit:
            if wtpage.get_slot_content("header") != "{{#invoke:Entity|header}}":
                wtpage.set_slot_content("header", "{{#invoke:Entity|header}}")
            if wtpage.get_slot_content("footer") != "{{#invoke:Entity|footer}}":
                wtpage.set_slot_content("footer", "{{#invoke:Entity|footer}}")

    wtsite.modify_search_results(
        "prefix",
        "Item:",
        # "semantic",
        # "[[IsA::Category:Category]]",
        modify,
        limit=300,
        comment="set default content of slot header and footer",
        log=True,
        dryrun=False,
    )


def text_replace():
    wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)

    def modify(wtpage: WtPage):
        edit = True
        if "#" in wtpage.title:
            edit = False
        if wtpage._page.redirect:
            edit = False
        if edit:
            for slot in wtpage._slots:
                content = wtpage.get_slot_content(slot)
                if isinstance(content, dict):
                    content = json.loads(json.dumps(content).replace("OSL", "OSW"))
                else:
                    content = content.replace("OSL", "OSW")
                wtpage.set_slot_content(slot, content)

    wtsite.modify_search_results(
        "semantic",
        # "[[IsA::Category:Category]]",
        "[[Item:+]]",
        # "prefix",
        # "Item:OSW",
        modify,
        limit=100,
        comment="replace OSL with OSW",
        log=True,
        dryrun=False,
    )


def move_page():
    wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)

    def modify(wtpage: WtPage):
        edit = True
        # print(wtpage.get_last_changed_time())
        if wtpage.get_last_changed_time() > datetime.fromisoformat(
            "2022-12-24T12:00:00+00:00"
        ):
            print("new")
        else:
            print("old")
            edit = False
        if "#" in wtpage.title:
            edit = False
        if wtpage._page.redirect:
            edit = False
        if edit:
            new_title = wtpage.title.replace("OSL", "OSW")
            wtpage.move(new_title=new_title, comment="replace OSL with OSW")

    wtsite.modify_search_results(
        "semantic",
        # "[[IsA::Category:Category]]",
        "[[~*File:OSL*]]",
        # "prefix",
        # "File:OSL",
        modify,
        limit=1000,
        comment="replace OSL with OSW",
        log=False,
        dryrun=True,
    )


# mass_page_edit()
# schema_renaming()
# slot_default_values()
# text_replace()
move_page()
