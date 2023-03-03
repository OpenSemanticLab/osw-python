import json
import os
from pathlib import Path
from utils import dict_to_json, json_to_dict
from quantityFunctions import QuantityFetcher, Quantities
from pprint import pprint

# 2: fetch quantities
# add path as an agument?
# QuantityFetcher() # uncomment this to fetch data and dump into json files

# 3: analyse wikidata 
wdict_obj = Quantities(json_to_dict('wdict')) # load data from json file
wdict_obj.analyzeWikidata()


# 4: create dict dbpedia -> wikidata
transform_dbpedia_to_wikidata = False
if transform_dbpedia_to_wikidata:
    dbpwdict = {}
    for dbp in dbpdict:
        w = ""
        for uri in dbpdict[dbp].get('http://www.w3.org/2002/07/owl#sameAs', []):
            if "wikidata.org/entity/" in uri: 
                w = uri
                break
        #print("{}: {}".format(dbp, w))
        dbpwdict[dbp] = w

    #create dict qudt -> wikidata
    qwdict = {}
    for w in wdict:
        if 'http://www.wikidata.org/prop/direct-normalized/P8393' in wdict[w]: qwdict[wdict[w]['http://www.wikidata.org/prop/direct-normalized/P8393'][0]] = w
    print(len(qwdict))
    qdbpdict = {}
    for q in qdict:
        if 'http://qudt.org/schema/qudt/dbpediaMatch' in qdict[q]:
            dbp = qdict[q]['http://qudt.org/schema/qudt/dbpediaMatch'][0]
            w = qwdict.get(q,"")
            if dbpwdict.get(dbp, "") != "" and dbpwdict.get(dbp, "") != w: 
                print("Wikidata Uri diff for {} and {}: {} vs {}".format(q,dbp,w,dbpwdict.get(dbp, "")))
                qwdict[q] = dbpwdict[dbp]
            qdbpdict[q] = dbp
    #print(len(qdbpdict))
    print(len(qwdict))
    for q in _qdict:
        if 'http://qudt.org/schema/qudt/dbpediaMatch' in _qdict[q]:
            dbp = _qdict[q]['http://qudt.org/schema/qudt/dbpediaMatch'][0]
            w = qwdict.get(q,"")
            if dbpwdict.get(dbp, "") != "" and dbpwdict.get(dbp, "") != w: 
                print("Wikidata Uri diff for {} and {}: {} vs {}".format(q,dbp,w,dbpwdict.get(dbp, "")))
                if q not in qwdict: 
                    print("add " + q)
                    qwdict[q] = dbpwdict[dbp]
            qdbpdict[q] = dbp
    print(len(qwdict)) #5 quantities have missing units or dimension in qudt but are defined in wikidata

    #check recommanded units
    #for w in wdict:
    #    wlabel = getLangLabel(wdict[w]["http://www.w3.org/2000/01/rdf-schema#label"], 'en')
    #    if "http://www.wikidata.org/prop/P8111" in wdict[w]:
    #        for wu in wdict[w]["http://www.wikidata.org/prop/P8111"]:
    #            wulabel = getLangLabel(wudict[wu]["http://www.w3.org/2000/01/rdf-schema#label"], 'en')
    #            print("{}: {}".format(wlabel, wulabel))
    #    else: print("{}: {}".format(wlabel, "UNDEFINED"))

    ucum_u_dict = {} #ucum to qudt unit
    for u in udict:
        if 'http://qudt.org/schema/qudt/ucumCode' in udict[u]: 
            if udict[u]['http://qudt.org/schema/qudt/ucumCode'][0] in ucum_u_dict:
                ucum = udict[u]['http://qudt.org/schema/qudt/ucumCode'][0]
                print("Warning: Conflict for {}: {} vs {}".format(ucum, u, ucum_u_dict[ucum]))
            ucum_u_dict[udict[u]['http://qudt.org/schema/qudt/ucumCode'][0]] = u
    print(len(udict))
    print(len(ucum_u_dict))
    #uwudict = {} # qudt unit to wiki data unit
    ucum_wu_dict = {} #ucum to wikidata unit
    for wu in wudict:
        if 'http://www.wikidata.org/prop/direct/P7825' in wudict[wu]:# and 'http://www.wikidata.org/prop/direct/P5061' in wudict[wu]:
            #print(wudict[wu]['http://www.wikidata.org/prop/direct/P5061'])
            for ucum in wudict[wu]['http://www.wikidata.org/prop/direct/P7825']:
                ucum_wu_dict[normUcumFracToLin(ucum)] = wu
    print(len(ucum_wu_dict))