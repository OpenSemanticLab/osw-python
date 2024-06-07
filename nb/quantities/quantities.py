from utils import json_to_dict
from quantityClasses import QuantityFetcher, Quantities

# import json
# import os
# from pathlib import Path
# from utils import dict_to_json, json_to_dict
# from pprint import pprint

# fetch quantities
# set fetch_data to True on first run
# './data' directory must exist
fetch_data = False
if fetch_data:
    QuantityFetcher()


# load data from json file
quantities = Quantities(
    json_to_dict("_ddict"),
    json_to_dict("_qdict"),
    json_to_dict("_udict"),
    json_to_dict("dbpdict"),
    json_to_dict("dCgsDict"),
    json_to_dict("dImpDict"),
    json_to_dict("dIsoDict"),
    json_to_dict("dSiDict"),
    json_to_dict("wdict"),
    json_to_dict("wstdict"),
    json_to_dict("wudict"),
)

# analyse wikidata
quantities.analyzeWikidata()

# create dict dbpedia -> wikidata
quantities.dbpediaToWikidata()

# merge qudt and wikidata hierarchy
quantities.mergeQudtAndWikidata()

# create wiki code
quantities.create_wiki_code()


# # mediawiki client import

# #print(qdict['http://qudt.org/vocab/quantitykind/Pressure'])
# #print(udict['http://qudt.org/vocab/unit/BARYE'])
# #print(ucum_wu_dict['kg.m-1.s-2'])
# #print(wudict['http://www.wikidata.org/entity/Q106696962'])
# #print_subject_object(udict, 'http://qudt.org/schema/qudt/ucumCode')
# #print(wdict[qwdict['http://qudt.org/vocab/quantitykind/ForcePerArea']])

# #import sys, os
# #sys.path.append(os.path.join(os.path.dirname(__file__), '../../src/'))
# #from wikitools import *
# import mwclient
# import getpass
# from pprint import pprint
# site = mwclient.Site('wiki-dev.open-semantic-lab.org', path='/w/')
# user = input("Enter wiki username")
# password = getpass.getpass("Enter wiki password")
# site.login(user, password)
# del user, password

# for p in pages:
#     print("Edit page {}".format(p['title']))
#     page = site.pages[p['title']]
#     page.edit(p['wikitext'])

# qdict['http://qudt.org/vocab/quantitykind/DimensionlessRatio']
# udict['http://qudt.org/vocab/unit/PERCENT']
# #wdict['http://www.wikidata.org/entity/Q11466']
