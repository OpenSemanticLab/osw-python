import sys
sys.path.append('../')
import src.wiki_tools as wt 
from pprint import pprint 


wikitext_org = """{{OslTemplate:LIMS/Device/Type
|timestamp=2022-10-10T00:00:00.000Z
|creator=C1;C2
|display_name=Test Term
|label=Device Test Type with Term
|label_lang_code=en
|description=Some description 
with line break
|category=Category:OSLa444b0eeb79140d58a836a7fc6fc940a
|relations={{OslTemplate:KB/Relation
|property=IsRelatedTo
|value=Term:OSL6b663c61c12d42e8be37d735dd2a869c
}}SomeText{{OslTemplate:KB/Relation
|property=IsRelatedTo
|value=Term:OSL6b663c61c12d42e8be37d735dd2a869c
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
if wikitext_2 == wikitext_org: print("wikitext_2 == wikitext_org")
else: print("wikitext_2 != wikitext_org")

content_dict_3 = wt.create_flat_content_structure_from_wikitext(wikitext_2)
pprint(content_dict_3)
wikitext_3 = wt.get_wikitext_from_flat_content_structure(content_dict_3)
print(wikitext_3)
if wikitext_3 == wikitext_2: print("wikitext_3 == wikitext_2")
else: print("wikitext_3 != wikitext_2")

content_dict_3[0]['OslTemplate:LIMS/Device/Type']['display_name'] = 'NEW VALUE'
print(wt.get_wikitext_from_flat_content_structure(content_dict_3))