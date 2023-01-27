import json
from utils import dict_to_json
from quantityFunctions import QuantityFetcher

quantity_fetcher = QuantityFetcher()


#2: fetch data (repeat section if error 'to many requests' occurs)
# status: passed
fetch = True
if fetch:
    limit = 999999999
    _qdict = quantity_fetcher.getQudtTypeDict('QuantityKind', limit)
    _udict = quantity_fetcher.getQudtTypeDict('Unit', limit)
    dSiDict = quantity_fetcher.getQudtTypeDict('QuantityKindDimensionVector_SI', limit)
    dIsoDict = quantity_fetcher.getQudtTypeDict('QuantityKindDimensionVector_ISO', limit)
    dImpDict = quantity_fetcher.getQudtTypeDict('QuantityKindDimensionVector_Imperial', limit)
    dCgsDict = quantity_fetcher.getQudtTypeDict('QuantityKindDimensionVector_CGS', limit)
    _ddict = {**dImpDict, **dCgsDict, **dIsoDict, **dSiDict} #merge dicts
    dict_to_json(_qdict, '_qdict')
    dict_to_json(_udict, '_udict')
    dict_to_json(dSiDict, 'dSiDict')
    dict_to_json(dIsoDict, 'dIsoDict')
    dict_to_json(dImpDict, 'dImpDict')
    dict_to_json(dCgsDict, 'dCgsDict')
    dict_to_json(_ddict, '_ddict')
    #for q in qdict: print(q)
    #for u in udict: print(u)
    #for d in ddict: print(d)
    print(len(_qdict))
    print(len(_udict))
    print(len(_ddict))

    #wdict1 = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>+ <http://www.wikidata.org/entity/Q107715>.") #195656 triplets found
    #wdict2 = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P8393> ?qudtid.") #48411 triplets found
    #wdict = {**wdict1, **wdict2} #merge dicts, 3966 results
    wdict = quantity_fetcher.get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>*/<http://www.wikidata.org/prop/direct/P8393> ?qudtid.") #quantities with qudt ref and their subq, 2484 results
    dict_to_json(wdict, 'wdict')
    print(len(wdict))
    #only subquantities
    #wdict = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>/<http://www.wikidata.org/prop/direct/P279>+ <http://www.wikidata.org/entity/Q107715>.")
    #print(len(wdict))
    #wstdict1 = get_sparql_wikidata_statement_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>+ <http://www.wikidata.org/entity/Q107715>.") #get statement object, 131347 triplets
    #wstdict2 = get_sparql_wikidata_statement_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P8393> ?qudtid.") #get statement object, 37775 triplets
    #wstdict = {**wstdict1, **wstdict2} #merge dicts, 3966 results
    wstdict = quantity_fetcher.get_sparql_wikidata_statement_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>*/<http://www.wikidata.org/prop/direct/P8393> ?qudtid.") #get statement object
    dict_to_json(wstdict, 'wstdict')
    print(len(wstdict))
    for st in wstdict:
        for p in wstdict[st]:
            o = wstdict[st][p]
            wdict[st][p] = o #replace statement with object
    wudict1 = quantity_fetcher.get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P31> <http://www.wikidata.org/entity/Q47574>.") #instance of unit of measurement: 1340 results
    wudict2 = quantity_fetcher.get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P5061> ?symbol.") #has unit symbol: 2230 results
    wudict3 = quantity_fetcher.get_sparql_triplets("https://query.wikidata.org/sparql", "?quantity <http://www.wikidata.org/prop/P8111>/<http://www.wikidata.org/prop/statement/P8111> ?subject.") #is recommended unit of measurement of: 294 results
    wudict4 = quantity_fetcher.get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/P111>/<http://www.wikidata.org/prop/statement/P111> ?quantity.") #has measured quantity: 3278 results
    wudict = {**wudict1, **wudict2, **wudict3, **wudict4} #merge dicts, 3966 results
    len(wudict)
    dict_to_json(wudict, 'wudict')
    
    #dbpdict = get_sparql_triplets("https://dbpedia.org/sparql/", "?subject <http://purl.org/dc/terms/subject> <http://dbpedia.org/resource/Category:Physical_quantities>.", limit=11000)
    #dbpdict = get_sparql_triplets("https://dbpedia.org/sparql/", "?subject <http://purl.org/dc/terms/subject>/<http://www.w3.org/2004/02/skos/core#broader> <http://dbpedia.org/resource/Category:Quantity>.")
    #endpoint is limited to 10000 results so we have to restrict the request to the relevant property
    dbpdict = quantity_fetcher.get_sparql_triplets("https://dbpedia.org/sparql/", "?subject <http://purl.org/dc/terms/subject>/<http://www.w3.org/2004/02/skos/core#broader> <http://dbpedia.org/resource/Category:Quantity>.", tpredicate="http://www.w3.org/2002/07/owl#sameAs")
    print(len(dbpdict))
    dict_to_json(dbpdict, 'dbpdict')
    

# # load data from json
# json.loads(wdict)  
# json.loads(wdict)  
# json.loads(wdict)  
# json.loads(wdict)  
# json.loads(wdict)  
# json.loads(wdict)  
# json.loads(wdict)  
# json.loads(wdict)  

# # #3: analyse wikidata 


# w_base_q = []
# no_unit = []
# no_dim = []
# for w in wdict:
#     #if 'http://www.wikidata.org/entity/Q107715' in wdict[w]['http://www.wikidata.org/prop/direct/P279']:
#     #    w_base_q.append(w)
#     sub_q = False
#     for sup in wdict[w]['http://www.wikidata.org/prop/direct/P279']:
#         if sup in wdict:
#             sub_q = True
#             break
#     if not sub_q: w_base_q.append(w)
#     if 'http://www.wikidata.org/prop/direct/P4020' not in wdict[w]: no_dim.append(w)
#     else: 
#         if 'http://www.wikidata.org/prop/direct/P8111' not in wdict[w] and wdict[w]['http://www.wikidata.org/prop/direct/P4020'] != "1":
#             no_unit.append(w)
        
# print(len(w_base_q))
# print(len(no_unit))
# print(len(no_dim))
# #for w in w_base_q:
# #    print(getLangLabel(wdict[w]["http://www.w3.org/2000/01/rdf-schema#label"], 'en'))
# ignore_list = []
# ignore_list.append('http://www.wikidata.org/entity/Q181175') #scalar quantity
# ignore_list.append('http://www.wikidata.org/entity/Q2672914') #vector quantity
# remove_wikidata_superclass('http://www.wikidata.org/entity/Q589446', 'http://www.wikidata.org/entity/Q3686031') #mass concentration is not subclass of amount concentration
# remove_wikidata_superclass('http://www.wikidata.org/entity/Q76378758', 'http://www.wikidata.org/entity/Q3686031') #mass concentration of water is not subclass of amount concentration
# remove_wikidata_superclass('http://www.wikidata.org/entity/Q13824', 'http://www.wikidata.org/entity/Q11465') #phase speed is not a velocity
# remove_wikidata_superclass('http://www.wikidata.org/entity/Q86508881', 'http://www.wikidata.org/entity/Q11465') #sound speed is not a velocity
# remove_wikidata_superclass('http://www.wikidata.org/entity/Q86508881', 'http://www.wikidata.org/entity/Q217361') #sound speed is not a group velocity Q217361
# remove_wikidata_superclass('http://www.wikidata.org/entity/Q1097654', 'http://www.wikidata.org/entity/Q11379') #rest mass is not an energy
# remove_wikidata_superclass('http://www.wikidata.org/entity/Q4128476', 'http://www.wikidata.org/entity/Q25288') #birth weight is a mass, not a force
# remove_wikidata_superclass('http://www.wikidata.org/entity/Q6795900', 'http://www.wikidata.org/entity/Q25288') #landing weight is a mass, not a force
# remove_wikidata_superclass('http://www.wikidata.org/entity/Q6795910', 'http://www.wikidata.org/entity/Q25288') #maximum ramp weight is a mass, not a force
# remove_wikidata_superclass('http://www.wikidata.org/entity/Q16815754', 'http://www.wikidata.org/entity/Q25288') #operating weight is a mass, not a force 
# remove_wikidata_superclass('http://www.wikidata.org/entity/Q55435676', 'http://www.wikidata.org/entity/Q275157') #fasting serum glucose level is a mass concentration, blood glucose is a amount concentration
# ignore_list.append('http://www.wikidata.org/entity/Q111811675') #area dublicate
# remove_wikidata_superclass('http://www.wikidata.org/entity/Q11500', 'http://www.wikidata.org/entity/Q111811675') #area is not subclass of dublicated area class (recursion)

# for w in wdict:
#     set_wikidata_base_and_super_quantities(w, ignore_list)
