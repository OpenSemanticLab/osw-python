from quantityFunctions import sparqlQuery
from quantityFunctions import get_sparql_triplets
from quantityFunctions import get_sparql_wikidata_statement_triplets
from quantityFunctions import qudtTypeQuery
from quantityFunctions import dict_append_tripl
from quantityFunctions import getQudtTypeDict
from quantityFunctions import print_subject_object
from quantityFunctions import getLangLabel
from quantityFunctions import get_property_wiki_page_name
from quantityFunctions import get_description
from quantityFunctions import set_main_and_invalid_units
from quantityFunctions import set_base_and_super_quantities
from quantityFunctions import validate_base_unit
from quantityFunctions import normUcumFracToLin
from quantityFunctions import set_wikidata_base_and_super_quantities
from quantityFunctions import remove_wikidata_superclass
#2: fetch data (passed)



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




