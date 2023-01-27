#!/usr/bin/env python
# coding: utf-8

# In[21]:


#1: declare functions
from SPARQLWrapper import SPARQLWrapper, POST, BASIC, JSON
import json
from pprint import pprint

def sparqlQuery(endpoint, query):
    sparql = SPARQLWrapper(endpoint)
    sparql.setMethod(POST)
    #print(query)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    #print(sparql.query())
    return sparql.query().convert()

def get_sparql_triplets(endpoint, where_statement, select_statement = "", inner_where_statement="?subject ?predicate ?object", tsubject="", tpredicate="", tobject="",limit=999999999):
    select_statement = ""
    if (tsubject == ""): select_statement += " ?subject"
    if (tpredicate == ""): select_statement += " ?predicate"
    if (tobject == ""): select_statement += " ?object"
    if (tsubject != ""): inner_where_statement = inner_where_statement.replace("?subject", "<" + tsubject + ">")
    if (tpredicate != ""): inner_where_statement = inner_where_statement.replace("?predicate", "<" + tpredicate + ">")
    if (tobject != ""): inner_where_statement = inner_where_statement.replace("?object", "<" + tobject + ">")
    query = """
        SELECT {{{select_statement}}}
        WHERE {
          {{{where_statement}}}
            {  
            SELECT {{{select_statement}}}
            WHERE {
                {{{inner_where_statement}}}
            }
          }
        }
        LIMIT {{{limit}}}
    """.replace("{{{select_statement}}}", select_statement).replace("{{{where_statement}}}", where_statement).replace("{{{inner_where_statement}}}", inner_where_statement).replace("{{{limit}}}", str(limit))
    print(query)
    #select distinct ?p ?o where {<http://dbpedia.org/resource/Amount_of_substance> ?p ?o} LIMIT 100
    triples = sparqlQuery(endpoint, query)
    #print(triples)
    tdict = {}
    print("{} triplets found".format(len(triples['results']['bindings'])))
    for t in triples['results']['bindings']:
        if (tsubject == ""): s = t['subject']['value']
        else: s = tsubject
        if (tpredicate == ""): p = t['predicate']['value']
        else: p = tpredicate
        if (tobject == ""): o = t['object']['value']
        else: o = tobject
        if 'xml:lang' in t['object']: o += "@" + t['object']['xml:lang']
        #print("{} {} {}".format(s,p,o))
        dict_append_tripl(tdict, s, p, o)
    #print(tdict)
    return tdict

def get_sparql_wikidata_statement_triplets(endpoint, where_statement ,limit=999999999):
    select_statement = "?subject ?predicate ?spredicate ?object"
    inner_where_statement="?subject ?predicate [?spredicate ?object; <http://wikiba.se/ontology#rank> ?rank]"
    query = """
        SELECT {{{select_statement}}}
        WHERE {
          {{{where_statement}}}
            {  
            SELECT {{{select_statement}}}
            WHERE {
                {{{inner_where_statement}}}
            }
          }
        }
        LIMIT {{{limit}}}
    """.replace("{{{select_statement}}}", select_statement).replace("{{{where_statement}}}", where_statement).replace("{{{inner_where_statement}}}", inner_where_statement).replace("{{{limit}}}", str(limit))
    print(query)
    triples = sparqlQuery(endpoint, query)
    #print(triples)
    tdict = {}
    print("{} triplets found".format(len(triples['results']['bindings'])))
    for t in triples['results']['bindings']:
        
        s = t['subject']['value']
        p = t['predicate']['value']
        sp = t['spredicate']['value']
        o = t['object']['value']
        if 'xml:lang' in t['object']: o += "@" + t['object']['xml:lang']
        #print("{} {}/{} {}".format(s,p,sp,o))
        if (p.split('/')[-1] == sp.split('/')[-1]): dict_append_tripl(tdict, s, p, o) #e.g.  http://www.wikidata.org/prop/P2347 and http://www.wikidata.org/prop/statement/value-normalized/P2347
    #print(tdict)
    return tdict

def qudtTypeQuery(qudt_type, limit=999999): # doesn't work anymore
    sparql = SPARQLWrapper("https://www.qudt.org/fuseki/qudt/sparql") #endpoint has changed from http to https
    sparql.setMethod(POST)

    query = """
        PREFIX qudt: <http://qudt.org/schema/qudt/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT ?subject ?predicate ?object
        WHERE {
          ?subject rdf:type qudt:{{{qudt_type}}} .
            {  
            SELECT ?subject ?predicate ?object
            WHERE {
                ?subject ?predicate ?object 
            }
          }
        }
        LIMIT {{{limit}}}
    """.replace("{{{qudt_type}}}",qudt_type).replace("{{{limit}}}",str(limit))
    #print(query)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    #print(sparql.query())
    return sparql.query().convert()

def dict_append_tripl(d, s, p, o):
    if not s in d: d[s] = {}
    if not p in d[s]: d[s][p] = []
    d[s][p].append(o)
    
def getQudtTypeDict(qudt_type, limit=999999):
    triples = qudtTypeQuery(qudt_type, limit)
    tdict = {}
    for t in triples['results']['bindings']:
        s = t['subject']['value']
        p = t['predicate']['value']
        o = t['object']['value']
        if 'xml:lang' in t['object']: o += "@" + t['object']['xml:lang']
        #print("{} {} {}".format(s,p,o))
        dict_append_tripl(tdict, s, p, o)
    return tdict

def print_subject_object(d, predicate_key):
    for s in d:
        print("{}: {}".format(s, d[s].get(predicate_key, "")))
        
def getLangLabel(labels, lang):
    for label in labels: 
        if '@' + lang in label: return label.replace('@' + lang, '')

def get_property_wiki_page_name(uri): return "Property:Has" + uri.split("/")[-1]

def get_description(q):
    text = ""
    if 'http://purl.org/dc/terms/description' in qdict[q]: text += qdict[q]['http://purl.org/dc/terms/description'][0]
    if 'http://qudt.org/schema/qudt/plainTextDescription' in qdict[q]:  text += "\n=== Plain text ===\n" + qdict[q]['http://qudt.org/schema/qudt/plainTextDescription'][0]
    if 'http://qudt.org/schema/qudt/latexDefinition' in qdict[q]: text += "\n=== Latex ===\n" + qdict[q]['http://qudt.org/schema/qudt/latexDefinition'][0]
    text = text.replace("\\(", "<math>").replace("\\)", "</math>").replace("\\", "\\")
    return text
#print(get_description('http://qudt.org/vocab/quantitykind/AmountOfSubstance'))
#print(get_description('http://qudt.org/vocab/quantitykind/HeatCapacity'))

def set_main_and_invalid_units(qId):
    q = qdict[qId]
    #print(json.dumps(q))
    main_units = []
    invalid_units = []
    units_by_conversion_factor = {}
    if 'http://qudt.org/schema/qudt/applicableUnit' in q and not isinstance(q['http://qudt.org/schema/qudt/applicableUnit'], type(None)):
        for u in q['http://qudt.org/schema/qudt/applicableUnit']:
            #print(udict[u])
            if 'http://qudt.org/schema/qudt/conversionMultiplier' in udict[u]:
                cf = udict[u]['http://qudt.org/schema/qudt/conversionMultiplier'][0]
                if float(cf) not in units_by_conversion_factor: units_by_conversion_factor[float(cf)] = []
                units_by_conversion_factor[float(cf)].append(u)
                if float(cf) == 1.0: main_units.append(u)
                elif float(cf) == 0.0: invalid_units.append(u)
            else: invalid_units.append(u)
            #print("{}: {}".format(u, cf))
    qdict[qId]['main_units'] = main_units 
    qdict[qId]['invalid_units'] = invalid_units 
    qdict[qId]['units_by_conversion_factor'] = dict(sorted(units_by_conversion_factor.items()))  
    #print("{}: mu:{} iu:{}".format(qId, main_units, invalid_units))

def set_base_and_super_quantities(qId, ignore = []):
    q = qdict[qId]
    #print(json.dumps(q))
    base_quantity = []
    subquantity_of = []
    if 'http://www.w3.org/2004/02/skos/core#broader' in q:
        for sup in q['http://www.w3.org/2004/02/skos/core#broader']:
            if sup in ignore: continue
            #print(sup)
            subquantity_of.append(sup)
            #has_super = True
            #while('http://www.w3.org/2004/02/skos/core#broader' in qdict[sup]):
            #    sup = qdict[sup]['http://www.w3.org/2004/02/skos/core#broader'][0]
            #    print("-> " + sup) 
            sup_base = set_base_and_super_quantities(sup, ignore)
            if (len(sup_base) == 0): base_quantity.extend(subquantity_of)
            else: base_quantity.extend(sup_base)
    qdict[qId]['base_quantity'] = base_quantity 
    qdict[qId]['subquantity_of'] = subquantity_of 
    if (len(base_quantity) > 1): print("WARNING: More than one base quantity for " + str(qId))
    return base_quantity

def validate_base_unit(q):
    units = []
    base_units = []
    #if not 'base_quantity' in qdict[q]: return True
    if len(qdict[q]['base_quantity']) == 0: return True
    units.extend(qdict[q].get('http://qudt.org/schema/qudt/applicableUnit', []))
    #print(qdict[q]['base_quantity'])
    base_units.extend(qdict[qdict[q]['base_quantity'][0]].get('http://qudt.org/schema/qudt/applicableUnit', []))
    sym_diff = set(units).symmetric_difference(set(base_units))
    if not len(sym_diff) == 0:
        #print("WARNING: Different units for subq {} ({}) and baseq {} ({})".format(q, len(units), qdict[q]['base_quantity'][0], len(base_units)))
        if (len(units) > len(base_units)): 
            print("WARNING: More units for subq {} than baseq {}".format(q, qdict[q]['base_quantity'][0]))
            diff = set(units).difference(set(base_units))
            print(diff)
            #print(qdict[qdict[q]['base_quantity'][0]]['http://qudt.org/schema/qudt/applicableUnit'])
            if 'http://qudt.org/schema/qudt/applicableUnit' in qdict[qdict[q]['base_quantity'][0]]: qdict[qdict[q]['base_quantity'][0]]['http://qudt.org/schema/qudt/applicableUnit'].extend(list(diff))
            else: qdict[qdict[q]['base_quantity'][0]]['http://qudt.org/schema/qudt/applicableUnit'] = list(diff)
            #qdict[qdict[q]['base_quantity'][0]]['http://qudt.org/schema/qudt/applicableUnit'] = qdict[qdict[q]['base_quantity'][0]].get('http://qudt.org/schema/qudt/applicableUnit', []).extend(list(diff))
            #print(qdict[qdict[q]['base_quantity'][0]]['http://qudt.org/schema/qudt/applicableUnit'])
    if not qdict[q]['http://qudt.org/schema/qudt/hasDimensionVector'][0] == qdict[qdict[q]['base_quantity'][0]]['http://qudt.org/schema/qudt/hasDimensionVector'][0]:
        print("WARNING: Different dim for subq {} and baseq {}".format(q, qdict[q]['base_quantity'][0]))
        
def normUcumFracToLin(ucum):
    result = ""
    fraction = False
    index = 0
    for c in ucum: #iterate over all chars
        skip = False
        if c == '/': 
            fraction = True
            if (index > 0): result += '.' #some ucums begin with a '/', no sep '.' needed
            skip = True
        if fraction:
            if c == '.' and ucum[index-1] not in ['0','1','2','3','4','5','6','7','8','9']: #exponent 1 is implicit, e.g. 'm.' -> 'm1.' 
                result += '-1' #assume 1 and invert it to -1
            if c == '(': 
                skip = True
            elif c == ')': 
                skip = True
                if index != len(ucum) - 1: 
                    print("Error: closing bracket not last char in {}".format(ucum))
                    return ucum
            elif c == '-':
                skip = True #make it positiv anyway
                print("Warning: negativ exponent in fraction in {}".format(ucum))
            elif c in ['0','1','2','3','4','5','6','7','8','9']:
                if ucum[index-1] in ['0','1','2','3','4','5','6','7','8','9']: #Todo: ignore factors like '/100cm2'
                    print("Error: double number in {}".format(ucum))
                    return ucum
                result += '-' #e.g. 's2' -> 's-2'
            if not skip: result += c
        else: result += c
        if not fraction and (c == '(' or c == ')'): 
            print("Error: brackets without fraktion in {}".format(ucum))
            return ucum
        index += 1
    if fraction and result[-1] not in ['0','1','2','3','4','5','6','7','8','9']: 
        result += '-1' #e.g. '/m': exponent 1 is implicit -> '/m-1'
    #if ucum != result: print("Normalize '{}' to '{}'".format(ucum, result)) 
    return result
#nomalize_ucum("kg/(m.s2)") 
        
def set_wikidata_base_and_super_quantities(wId, ignore = []):
    w = wdict[wId]
    #print(json.dumps(q))
    base_quantity = []
    subquantity_of = []
    sup_base = []
    if 'http://www.wikidata.org/prop/P279' in w:
        for sup in w['http://www.wikidata.org/prop/P279']:
            if sup in ignore: continue
            if sup not in wdict: continue
            #print("{} -> {}".format(wId, sup))
            subquantity_of.append(sup)
            ignore.append(w) #prevent circular dep.
            sup_base.extend(set_wikidata_base_and_super_quantities(sup, ignore))
    if (len(sup_base) == 0): base_quantity.extend(subquantity_of)
    else: base_quantity.extend(sup_base)
    base_quantity = list(dict.fromkeys(base_quantity)) #remove duplicate
    wdict[wId]['base_quantity'] = base_quantity 
    wdict[wId]['subquantity_of'] = subquantity_of 
    if (len(base_quantity) > 1): print("WARNING: More than one base quantity for {}: {}".format(wId, base_quantity))
    return base_quantity

def remove_wikidata_superclass(w, sup):
    if sup in wdict[w]['http://www.wikidata.org/prop/P279']: wdict[w]['http://www.wikidata.org/prop/P279'].remove(sup) 
    


# In[22]:


#2: fetch data (repeat section if error 'to many requests' occurs)

limit = 999999999
_qdict = getQudtTypeDict('QuantityKind', limit)
_udict = getQudtTypeDict('Unit', limit)
dSiDict = getQudtTypeDict('QuantityKindDimensionVector_SI', limit)
dIsoDict = getQudtTypeDict('QuantityKindDimensionVector_ISO', limit)
dImpDict = getQudtTypeDict('QuantityKindDimensionVector_Imperial', limit)
dCgsDict = getQudtTypeDict('QuantityKindDimensionVector_CGS', limit)
_ddict = {**dImpDict, **dCgsDict, **dIsoDict, **dSiDict} #merge dicts
#for q in qdict: print(q)
#for u in udict: print(u)
#for d in ddict: print(d)
print(len(_qdict))
print(len(_udict))
print(len(_ddict))

#wdict1 = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>+ <http://www.wikidata.org/entity/Q107715>.") #195656 triplets found
#wdict2 = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P8393> ?qudtid.") #48411 triplets found
#wdict = {**wdict1, **wdict2} #merge dicts, 3966 results
wdict = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>*/<http://www.wikidata.org/prop/direct/P8393> ?qudtid.") #quantities with qudt ref and their subq, 2484 results
print(len(wdict))
#only subquantities
#wdict = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>/<http://www.wikidata.org/prop/direct/P279>+ <http://www.wikidata.org/entity/Q107715>.")
#print(len(wdict))
#wstdict1 = get_sparql_wikidata_statement_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>+ <http://www.wikidata.org/entity/Q107715>.") #get statement object, 131347 triplets
#wstdict2 = get_sparql_wikidata_statement_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P8393> ?qudtid.") #get statement object, 37775 triplets
#wstdict = {**wstdict1, **wstdict2} #merge dicts, 3966 results
wstdict = get_sparql_wikidata_statement_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>*/<http://www.wikidata.org/prop/direct/P8393> ?qudtid.") #get statement object
print(len(wstdict))
for st in wstdict:
    for p in wstdict[st]:
        o = wstdict[st][p]
        wdict[st][p] = o #replace statement with object
wudict1 = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P31> <http://www.wikidata.org/entity/Q47574>.") #instance of unit of measurement: 1340 results
wudict2 = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P5061> ?symbol.") #has unit symbol: 2230 results
wudict3 = get_sparql_triplets("https://query.wikidata.org/sparql", "?quantity <http://www.wikidata.org/prop/P8111>/<http://www.wikidata.org/prop/statement/P8111> ?subject.") #is recommended unit of measurement of: 294 results
wudict4 = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/P111>/<http://www.wikidata.org/prop/statement/P111> ?quantity.") #has measured quantity: 3278 results
wudict = {**wudict1, **wudict2, **wudict3, **wudict4} #merge dicts, 3966 results
len(wudict)

#dbpdict = get_sparql_triplets("https://dbpedia.org/sparql/", "?subject <http://purl.org/dc/terms/subject> <http://dbpedia.org/resource/Category:Physical_quantities>.", limit=11000)
#dbpdict = get_sparql_triplets("https://dbpedia.org/sparql/", "?subject <http://purl.org/dc/terms/subject>/<http://www.w3.org/2004/02/skos/core#broader> <http://dbpedia.org/resource/Category:Quantity>.")
#endpoint is limited to 10000 results so we have to restrict the request to the relevant property
dbpdict = get_sparql_triplets("https://dbpedia.org/sparql/", "?subject <http://purl.org/dc/terms/subject>/<http://www.w3.org/2004/02/skos/core#broader> <http://dbpedia.org/resource/Category:Quantity>.", tpredicate="http://www.w3.org/2002/07/owl#sameAs")
print(len(dbpdict))


# In[24]:


#3: analyse wikidata 

w_base_q = []
no_unit = []
no_dim = []
for w in wdict:
    #if 'http://www.wikidata.org/entity/Q107715' in wdict[w]['http://www.wikidata.org/prop/direct/P279']:
    #    w_base_q.append(w)
    sub_q = False
    for sup in wdict[w]['http://www.wikidata.org/prop/direct/P279']:
        if sup in wdict:
            sub_q = True
            break
    if not sub_q: w_base_q.append(w)
    if 'http://www.wikidata.org/prop/direct/P4020' not in wdict[w]: no_dim.append(w)
    else: 
        if 'http://www.wikidata.org/prop/direct/P8111' not in wdict[w] and wdict[w]['http://www.wikidata.org/prop/direct/P4020'] != "1":
            no_unit.append(w)
        
print(len(w_base_q))
print(len(no_unit))
print(len(no_dim))
#for w in w_base_q:
#    print(getLangLabel(wdict[w]["http://www.w3.org/2000/01/rdf-schema#label"], 'en'))
ignore_list = []
ignore_list.append('http://www.wikidata.org/entity/Q181175') #scalar quantity
ignore_list.append('http://www.wikidata.org/entity/Q2672914') #vector quantity
remove_wikidata_superclass('http://www.wikidata.org/entity/Q589446', 'http://www.wikidata.org/entity/Q3686031') #mass concentration is not subclass of amount concentration
remove_wikidata_superclass('http://www.wikidata.org/entity/Q76378758', 'http://www.wikidata.org/entity/Q3686031') #mass concentration of water is not subclass of amount concentration
remove_wikidata_superclass('http://www.wikidata.org/entity/Q13824', 'http://www.wikidata.org/entity/Q11465') #phase speed is not a velocity
remove_wikidata_superclass('http://www.wikidata.org/entity/Q86508881', 'http://www.wikidata.org/entity/Q11465') #sound speed is not a velocity
remove_wikidata_superclass('http://www.wikidata.org/entity/Q86508881', 'http://www.wikidata.org/entity/Q217361') #sound speed is not a group velocity Q217361
remove_wikidata_superclass('http://www.wikidata.org/entity/Q1097654', 'http://www.wikidata.org/entity/Q11379') #rest mass is not an energy
remove_wikidata_superclass('http://www.wikidata.org/entity/Q4128476', 'http://www.wikidata.org/entity/Q25288') #birth weight is a mass, not a force
remove_wikidata_superclass('http://www.wikidata.org/entity/Q6795900', 'http://www.wikidata.org/entity/Q25288') #landing weight is a mass, not a force
remove_wikidata_superclass('http://www.wikidata.org/entity/Q6795910', 'http://www.wikidata.org/entity/Q25288') #maximum ramp weight is a mass, not a force
remove_wikidata_superclass('http://www.wikidata.org/entity/Q16815754', 'http://www.wikidata.org/entity/Q25288') #operating weight is a mass, not a force 
remove_wikidata_superclass('http://www.wikidata.org/entity/Q55435676', 'http://www.wikidata.org/entity/Q275157') #fasting serum glucose level is a mass concentration, blood glucose is a amount concentration
ignore_list.append('http://www.wikidata.org/entity/Q111811675') #area dublicate
remove_wikidata_superclass('http://www.wikidata.org/entity/Q11500', 'http://www.wikidata.org/entity/Q111811675') #area is not subclass of dublicated area class (recursion)

for w in wdict:
    set_wikidata_base_and_super_quantities(w, ignore_list)


# In[26]:


#5: create dict dbpedia -> wikidata
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


# In[27]:


#4: merge qudt and wikidata hierarchy
qdict = _qdict.copy()
udict = _udict.copy()
ddict = _ddict.copy()

#print(get_property_wiki_page_name(qId))
#wt = ""

for q in qdict:
    if 'http://qudt.org/schema/qudt/applicableUnit' in qdict[q] and isinstance(qdict[q]['http://qudt.org/schema/qudt/applicableUnit'], type(None)):
        qdict[q]['http://qudt.org/schema/qudt/applicableUnit'] = []
        
remove_list = []
for q in qdict:
    invalid = False
    if not 'http://qudt.org/schema/qudt/hasDimensionVector' in qdict[q]:
        #print("Invalid (no dim): " + q)
        invalid = True
    if invalid: remove_list.append(q)

#manual corrections
remove_list.append('http://qudt.org/vocab/quantitykind/ElectricField') #dublicate of http://qudt.org/vocab/quantitykind/ElectricFieldStrength
remove_list.append('http://qudt.org/vocab/quantitykind/InverseTime')
for q in remove_list: del qdict[q]
if 'http://qudt.org/vocab/quantitykind/InformationFlowRate' in qdict['http://qudt.org/vocab/quantitykind/DataRate']['http://www.w3.org/2004/02/skos/core#broader']:
    qdict['http://qudt.org/vocab/quantitykind/DataRate']['http://www.w3.org/2004/02/skos/core#broader'].remove('http://qudt.org/vocab/quantitykind/InformationFlowRate') #invalid super quantity
qdict['http://qudt.org/vocab/quantitykind/MassFraction']['http://www.w3.org/2004/02/skos/core#broader'] = ['http://qudt.org/vocab/quantitykind/DimensionlessRatio']
qdict['http://qudt.org/vocab/quantitykind/MassFractionOfWater']['http://www.w3.org/2004/02/skos/core#broader'] = ['http://qudt.org/vocab/quantitykind/MassFraction']

#udict['http://qudt.org/vocab/unit/UNITLESS']['http://qudt.org/schema/qudt/ucumCode'] = udict['http://qudt.org/vocab/unit/UNITLESS'].get('http://qudt.org/schema/qudt/ucumCode', []).append('[1]')
#udict['http://qudt.org/vocab/unit/PERCENT']['http://qudt.org/schema/qudt/conversionMultiplier'] = udict['http://qudt.org/vocab/unit/PERCENT'].get('http://qudt.org/schema/qudt/conversionMultiplier', []).append('0.01')
udict['http://qudt.org/vocab/unit/UNITLESS']['http://qudt.org/schema/qudt/ucumCode'] = ['[1]']
udict['http://qudt.org/vocab/unit/PERCENT']['http://qudt.org/schema/qudt/conversionMultiplier'] = ['0.01']

for q in qdict:
    #print(q)
    set_main_and_invalid_units(q)
    set_base_and_super_quantities(q, remove_list)

#retrieve hierarchy from wikidata
qwdict_inv = {v: k for k, v in qwdict.items()}
for q in qdict:
    if (len(qdict[q]['base_quantity']) > 0): sup = qdict[q]['base_quantity'][0]
    else: sup = "";
    if q in qwdict:
        w = qwdict[q]
        if w in wdict:
            if (len(wdict[w]['base_quantity']) > 0): wsup = wdict[w]['base_quantity'][0]
            else: wsup = "";
            if wsup in qwdict_inv:
                wsup_q = qwdict_inv[wsup]
                if sup != wsup_q:
                    if sup == "": 
                        #print("new base_quantity {} for {}".format(wsup_q, q))
                        if wsup_q in qdict:
                            qdict[q]['base_quantity'] = [wsup_q]
                            qdict[q]['subquantity_of'] = [wsup_q]
                        i = 1
                    elif wsup_q in qdict and sup in qdict[wsup_q]['base_quantity']: 
                        #print("Resolveable Diff {} <-> {} for {}".format(sup, wsup_q, q))
                        i = 1
                    else: print("Unresolveable Diff {} <-> {} for {}".format(sup, wsup_q, q))
                #else: print("No diff {} {}".format(sup, wsup_q))
            #print("Missing in inv: {}".format(wsup))
        else: print("Missing: {}".format(w))
#manual corrections
qdict['http://qudt.org/vocab/quantitykind/DynamicViscosity']['base_quantity'].remove('http://qudt.org/vocab/quantitykind/Force')
qdict['http://qudt.org/vocab/quantitykind/DynamicViscosity']['subquantity_of'].remove('http://qudt.org/vocab/quantitykind/Force')
        
for q in qdict:
    #print(q)
    set_main_and_invalid_units(q)
    validate_base_unit(q)
    
remove_list = []
for q in qdict:
    invalid = False
    if not 'http://qudt.org/schema/qudt/applicableUnit' in qdict[q]: 
        print("Invalid (no units): " + q)
        invalid = True    
    if invalid: remove_list.append(q)
        
for q in remove_list: del qdict[q]

for q in qdict:
    validate_base_unit(q)

broader_cluster = []
dim_cluster = []
for q in qdict: 
    if len(qdict[q]['base_quantity']) > 0: broader_cluster.append(qdict[q]['base_quantity'][0])
    else: broader_cluster.append(q)
    dim_cluster.append(qdict[q]['http://qudt.org/schema/qudt/hasDimensionVector'][0])

#q = 'http://qudt.org/vocab/quantitykind/Density'
#set_main_and_invalid_units(q)
#print(qdict[q])

#q = 'http://qudt.org/vocab/quantitykind/AmbientPressure'
#set_base_and_super_quantities(q)
#print(qdict[q])
#print(qdict['http://qudt.org/vocab/quantitykind/Pressure'])
#print(qdict['http://qudt.org/vocab/quantitykind/ForcePerArea'])


# In[28]:


from collections import Counter
bres = Counter(broader_cluster)
bres = {k: v for k, v in sorted(bres.items(), key=lambda item: item[1], reverse=True)}
dres = Counter(dim_cluster)
dres = {k: v for k, v in sorted(dres.items(), key=lambda item: item[1], reverse=True)}
stats = {}
for dim in dres:
    stats[dim] = {'total': dres[dim], 'broader_cluster_member_count': 0, 'broader_cluster':{}}
for q in bres:
    d = qdict[q]['http://qudt.org/schema/qudt/hasDimensionVector'][0]
    stats[d]['broader_cluster'][q] = {'member_count': bres[q]}
    stats[d]['broader_cluster_member_count'] += bres[q]
stats


# In[29]:


for q in qdict:
    if 'http://qudt.org/vocab/dimensionvector/A0E0L3I0M0H0T0D0' in qdict[q]['http://qudt.org/schema/qudt/hasDimensionVector']:
        print(q)


# In[30]:


#6: create wiki code

def get_wikipage_dict(q):
    wt = {'title': get_property_wiki_page_name(q), 'content': [{'OslTemplate:Property/Quantity':{}}]}
    wtq = wt['content'][0]['OslTemplate:Property/Quantity']
    wtq['label'] = qdict[q]['http://www.w3.org/2000/01/rdf-schema#label'][0] 
    if q in qwdict and 'http://www.w3.org/2000/01/rdf-schema#label' in wdict[qwdict[q]]:
        #wtq['label_de'] = getLangLabel(wdict[qwdict[q]]['http://www.w3.org/2000/01/rdf-schema#label'], 'de')
        wtq['label'] = wdict[qwdict[q]]['http://www.w3.org/2000/01/rdf-schema#label']
        for label in wtq['label']: 
            if any(substring in label for substring in ["@zh-cn", "@ms-arab", "@sms", "@smj"]): wtq['label'].remove(label) #unsupported
    else: wtq['label'] = qdict[q]['http://www.w3.org/2000/01/rdf-schema#label'][0] + "@en"         
    wtq['ontology_iri'] = [q]
    if q in qwdict: wtq['ontology_iri'].append(qwdict[q])
    if q in qdbpdict: wtq['ontology_iri'].append(qdbpdict[q])
    wtq['description'] = get_description(q)
    if len(qdict[q]['base_quantity']) == 0:
        wtq['main_unit'] = ""
        wtq['alternative_names'] = []
        wtq['main_unit_ontology_iri'] = []
        wtq['alternative_units'] = []
        units = []
        unit_uris = []
        for cf in qdict[q]['units_by_conversion_factor']:
            wtu = {'alternative_names': [], 'ontology_iri': [], 'use_as_display_unit': 'Yes', 'use_as_input_unit': 'Yes'}
            valid = False
            first = True
            for index, u in enumerate(qdict[q]['units_by_conversion_factor'][cf]):
                #print(u)
                unit_uris.append(u)
                if 'http://qudt.org/schema/qudt/ucumCode' not in udict[u]: 
                    print("Warning: Unit {} without ucum code ignored".format(u))
                    continue
                ucum = udict[u]['http://qudt.org/schema/qudt/ucumCode'][0]
                if '{' in ucum: 
                    print("Warning: Unit {} without invalid char ignored".format(u))
                    continue
                sym = ucum
                if ('[' in sym):
                    print("Warning: Imperial Unit {} only for reference".format(u))
                    wtu['use_as_display_unit'] = 'No'
                    wtu['use_as_input_unit'] = 'No'
                #if ucum in ucum_wu_dict:
                #    if 'http://www.wikidata.org/prop/direct/P5061' in wudict[ucum_wu_dict[ucum]]: 
                #        sym = getLangLabel(wudict[ucum_wu_dict[ucum]]['http://www.wikidata.org/prop/direct/P5061'],'en')
                #    unit_uris.append(ucum_wu_dict[ucum])
                #else: print("Not found: {}".format(ucum))
                units.append(sym)
                if cf == 1.0:
                    if first: 
                        wtq['main_unit'] = sym
                        first = False
                    else: 
                        if len(sym) < len(wtq['main_unit']): #policy: use shortes ucum as main symbol
                            wtq['alternative_names'].append(wtq['main_unit'])
                            wtq['main_unit'] = sym
                        else: wtq['alternative_names'].append(sym)
                    wtq['main_unit_ontology_iri'].append(u)
                if cf != 1.0:
                    wtu['factor'] = str(1.0/cf) #Semantic Mediawiki uses inverse conversion factor
                    if first: 
                        wtu['unit'] = sym
                        first = False
                    else: 
                        if len(sym) < len(wtu['unit']): #policy: use shortes ucum as main symbol
                            wtu['alternative_names'].append(wtu['unit'])
                            wtu['unit'] = sym
                        else: wtu['alternative_names'].append(sym)
                    wtu['ontology_iri'].append(u)
                valid = True
            if cf != 1.0 and valid: wtq['alternative_units'].append({'OslTemplate:Property/Quantity/Unit':wtu})
    else:
        wtq['base_quantity'] = get_property_wiki_page_name(qdict[q]['base_quantity'][0])
        wtq['subquantity_of']=[]
        for sup in qdict[q]['subquantity_of']: wtq['subquantity_of'].append(get_property_wiki_page_name(sup))
        wtq['display_units'] = []
        wtq['input_units'] = []
        for cf in qdict[q]['units_by_conversion_factor']:
            for index, u in enumerate(qdict[q]['units_by_conversion_factor'][cf]):
                if 'http://qudt.org/schema/qudt/ucumCode' not in udict[u]: 
                    print("Warning: Unit {} without ucum code ignored".format(u))
                    continue
                ucum = udict[u]['http://qudt.org/schema/qudt/ucumCode'][0]
                sym = ucum
                if ('[' in sym):
                    print("Warning: Imperial Unit {} ignored".format(u))
                    continue
                wtq['display_units'].append(sym)
                wtq['input_units'].append(sym)
    return wt

def get_wikitext_from_wikipage_dict(d):
    wt = ""
    for key, value in d.items():
        #print("key: {}, valuetype: {}, value: {}".format(key, type(value), "")) 
        if isinstance(value,dict): 
            #print("dict")
            wt += "\n{{" + key
            wt += get_wikitext_from_wikipage_dict(value)
            wt += "\n}}"
        elif isinstance(value,list): 
            #print("list")
            wt += "\n|{}=".format(key)
            for index, element in enumerate(value):
                if isinstance(element,dict): 
                    wt += get_wikitext_from_wikipage_dict(element)
                    #wt += "\n{{" + element
                    #wt += get_wikitext_from_dict(element)
                    #wt += "\n}}"  
                else:
                    if index > 0: wt += ";"
                    wt += element
        else: 
            #print("literal")
            wt += "\n|{}={}".format(key, value)
    return wt

def set_wikitext_from_content(p):
    wt = ""
    for content_element in p['content']:
        if isinstance(content_element,dict): 
            wt += get_wikitext_from_wikipage_dict(content_element)
        elif isinstance(content_element,str): wt += "\n" + content_element
        else: print("Error: content element is not dict or string: {}".format(content_element))
    p['wikitext'] = wt
    return wt

q_list = []
#q_list.append('http://qudt.org/vocab/quantitykind/AmbientPressure')
#q_list.append('http://qudt.org/vocab/quantitykind/Pressure')
#q_list.append('http://qudt.org/vocab/quantitykind/ForcePerArea')
#q_list.append('http://qudt.org/vocab/quantitykind/Time')
#q_list.append('http://qudt.org/vocab/quantitykind/Temperature')
q_list.append('http://qudt.org/vocab/quantitykind/Temperature')
#q_list.append('http://qudt.org/vocab/quantitykind/Force')
#q_list.append('http://qudt.org/vocab/quantitykind/Stress')
#q_list.append('http://qudt.org/vocab/quantitykind/ShearStress')
#q_list.append('http://qudt.org/vocab/quantitykind/NormalStress')
#q_list.append('http://qudt.org/vocab/quantitykind/DimensionlessRatio')
#q_list.append('http://qudt.org/vocab/quantitykind/MoleFraction')
#q_list.append('http://qudt.org/vocab/quantitykind/LiquidVolume')
#q_list.append('http://qudt.org/vocab/quantitykind/Volume')
pages = []
for q in q_list:
    p = get_wikipage_dict(q)
    pprint(p)#json.dumps(p))
    wiki_text = set_wikitext_from_content(p)
    #print(wiki_text)
    pages.append(p)


# In[ ]:


#print(qdict['http://qudt.org/vocab/quantitykind/Pressure'])
#print(udict['http://qudt.org/vocab/unit/BARYE'])
#print(ucum_wu_dict['kg.m-1.s-2'])
#print(wudict['http://www.wikidata.org/entity/Q106696962'])
#print_subject_object(udict, 'http://qudt.org/schema/qudt/ucumCode')
#print(wdict[qwdict['http://qudt.org/vocab/quantitykind/ForcePerArea']])


# In[ ]:


#import sys, os
#sys.path.append(os.path.join(os.path.dirname(__file__), '../../src/'))
#from wikitools import *
import mwclient
import getpass
from pprint import pprint
site = mwclient.Site('wiki-dev.open-semantic-lab.org', path='/w/')
user = input("Enter wiki username")
password = getpass.getpass("Enter wiki password")
site.login(user, password)
del user, password


# In[737]:


for p in pages:
    print("Edit page {}".format(p['title']))
    page = site.pages[p['title']]
    page.edit(p['wikitext'])


# In[28]:


qdict['http://qudt.org/vocab/quantitykind/DimensionlessRatio']
udict['http://qudt.org/vocab/unit/PERCENT']
#wdict['http://www.wikidata.org/entity/Q11466']


# In[ ]:




