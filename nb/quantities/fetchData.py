import json
import os
from pathlib import Path
from utils import dict_to_json, json_to_dict
from quantityFunctions import QuantityFetcher, Quantities
from pprint import pprint

# 2: fetch quantities
# set fetch_data to True on first run
fetch_data = False # './data' directory must exist
if fetch_data:
    QuantityFetcher() 


# load data from json file
quantities = Quantities(
        json_to_dict('_ddict'),     
        json_to_dict('_qdict'),     
        json_to_dict('_udict'),     
        json_to_dict('dbpdict'),  
        json_to_dict('dCgsDict'),
        json_to_dict('dImpDict'),
        json_to_dict('dIsoDict'),
        json_to_dict('dSiDict'),
        json_to_dict('wdict'),
        json_to_dict('wstdict'),
        json_to_dict('wudict')
    ) 

# 3: analyse wikidata 
quantities.analyzeWikidata()

# 4: create dict dbpedia -> wikidata
quantities.dbpediaToWikidata()

# 5: merge qudt and wikidata hierarchy
quantities.mergeQudtAndWikidata()

# 6 create wiki code
quantities.create_wiki_code()