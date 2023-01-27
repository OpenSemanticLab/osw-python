#1: declare functions
from SPARQLWrapper import SPARQLWrapper, POST, BASIC, JSON
import json
from pprint import pprint

class QuantityFetcher():
    def sparqlQuery(self, endpoint, query):
        sparql = SPARQLWrapper(endpoint)
        sparql.setMethod(POST)
        #print(query)
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        #print(sparql.query())
        return sparql.query().convert()

    def get_sparql_triplets(self, endpoint, where_statement, select_statement = "", inner_where_statement="?subject ?predicate ?object", tsubject="", tpredicate="", tobject="",limit=999999999):
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
        triples = self.sparqlQuery(endpoint, query)
        #print(triples)
        self.tdict = {}
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
            self.dict_append_tripl(self.tdict, s, p, o)
        #print(self.tdict)
        return self.tdict

    def get_sparql_wikidata_statement_triplets(self, endpoint, where_statement ,limit=999999999):
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
        triples = self.sparqlQuery(endpoint, query)
        #print(triples)
        self.tdict = {}
        print("{} triplets found".format(len(triples['results']['bindings'])))
        for t in triples['results']['bindings']:
            
            s = t['subject']['value']
            p = t['predicate']['value']
            sp = t['spredicate']['value']
            o = t['object']['value']
            if 'xml:lang' in t['object']: o += "@" + t['object']['xml:lang']
            #print("{} {}/{} {}".format(s,p,sp,o))
            if (p.split('/')[-1] == sp.split('/')[-1]): self.dict_append_tripl(self.tdict, s, p, o) #e.g.  http://www.wikidata.org/prop/P2347 and http://www.wikidata.org/prop/statement/value-normalized/P2347
        #print(self.tdict)
        return self.tdict

    def qudtTypeQuery(self, qudt_type, limit=999999): # doesn't work anymore
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

    def dict_append_tripl(self, d, s, p, o):
        if not s in d: d[s] = {}
        if not p in d[s]: d[s][p] = []
        d[s][p].append(o)
        
    def getQudtTypeDict(self, qudt_type, limit=999999):
        triples = self.qudtTypeQuery(qudt_type, limit)
        self.tdict = {}
        for t in triples['results']['bindings']:
            s = t['subject']['value']
            p = t['predicate']['value']
            o = t['object']['value']
            if 'xml:lang' in t['object']: o += "@" + t['object']['xml:lang']
            #print("{} {} {}".format(s,p,o))
            self.dict_append_tripl(self.tdict, s, p, o)
        return self.tdict

    def print_subject_object(self, d, predicate_key):
        for s in d:
            print("{}: {}".format(s, d[s].get(predicate_key, "")))
            
    def getLangLabel(self, labels, lang):
        for label in labels: 
            if '@' + lang in label: return label.replace('@' + lang, '')

    def get_property_wiki_page_name(self, uri): return "Property:Has" + uri.split("/")[-1]

    def get_description(self, q):
        text = ""
        if 'http://purl.org/dc/terms/description' in self.qdict[q]: text += self.qdict[q]['http://purl.org/dc/terms/description'][0]
        if 'http://qudt.org/schema/qudt/plainTextDescription' in self.qdict[q]:  text += "\n=== Plain text ===\n" + self.qdict[q]['http://qudt.org/schema/qudt/plainTextDescription'][0]
        if 'http://qudt.org/schema/qudt/latexDefinition' in self.qdict[q]: text += "\n=== Latex ===\n" + self.qdict[q]['http://qudt.org/schema/qudt/latexDefinition'][0]
        text = text.replace("\\(", "<math>").replace("\\)", "</math>").replace("\\", "\\")
        return text
    #print(self.get_description('http://qudt.org/vocab/quantitykind/AmountOfSubstance'))
    #print(self.get_description('http://qudt.org/vocab/quantitykind/HeatCapacity'))

    def set_main_and_invalid_units(self, qId):
        q = self.qdict[qId]
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
        self.qdict[qId]['main_units'] = main_units 
        self.qdict[qId]['invalid_units'] = invalid_units 
        self.qdict[qId]['units_by_conversion_factor'] = dict(sorted(units_by_conversion_factor.items()))  
        #print("{}: mu:{} iu:{}".format(qId, main_units, invalid_units))

    def set_base_and_super_quantities(self, qId, ignore = []):
        q = self.qdict[qId]
        #print(json.dumps(q))
        base_quantity = []
        subquantity_of = []
        if 'http://www.w3.org/2004/02/skos/core#broader' in q:
            for sup in q['http://www.w3.org/2004/02/skos/core#broader']:
                if sup in ignore: continue
                #print(sup)
                subquantity_of.append(sup)
                #has_super = True
                #while('http://www.w3.org/2004/02/skos/core#broader' in self.qdict[sup]):
                #    sup = self.qdict[sup]['http://www.w3.org/2004/02/skos/core#broader'][0]
                #    print("-> " + sup) 
                sup_base = self.set_base_and_super_quantities(sup, ignore)
                if (len(sup_base) == 0): base_quantity.extend(subquantity_of)
                else: base_quantity.extend(sup_base)
        self.qdict[qId]['base_quantity'] = base_quantity 
        self.qdict[qId]['subquantity_of'] = subquantity_of 
        if (len(base_quantity) > 1): print("WARNING: More than one base quantity for " + str(qId))
        return base_quantity

    def validate_base_unit(self, q):
        units = []
        base_units = []
        #if not 'base_quantity' in self.qdict[q]: return True
        if len(self.qdict[q]['base_quantity']) == 0: return True
        units.extend(self.qdict[q].get('http://qudt.org/schema/qudt/applicableUnit', []))
        #print(self.qdict[q]['base_quantity'])
        base_units.extend(self.qdict[self.qdict[q]['base_quantity'][0]].get('http://qudt.org/schema/qudt/applicableUnit', []))
        sym_diff = set(units).symmetric_difference(set(base_units))
        if not len(sym_diff) == 0:
            #print("WARNING: Different units for subq {} ({}) and baseq {} ({})".format(q, len(units), self.qdict[q]['base_quantity'][0], len(base_units)))
            if (len(units) > len(base_units)): 
                print("WARNING: More units for subq {} than baseq {}".format(q, self.qdict[q]['base_quantity'][0]))
                diff = set(units).difference(set(base_units))
                print(diff)
                #print(self.qdict[self.qdict[q]['base_quantity'][0]]['http://qudt.org/schema/qudt/applicableUnit'])
                if 'http://qudt.org/schema/qudt/applicableUnit' in self.qdict[self.qdict[q]['base_quantity'][0]]: self.qdict[self.qdict[q]['base_quantity'][0]]['http://qudt.org/schema/qudt/applicableUnit'].extend(list(diff))
                else: self.qdict[self.qdict[q]['base_quantity'][0]]['http://qudt.org/schema/qudt/applicableUnit'] = list(diff)
                #self.qdict[self.qdict[q]['base_quantity'][0]]['http://qudt.org/schema/qudt/applicableUnit'] = self.qdict[self.qdict[q]['base_quantity'][0]].get('http://qudt.org/schema/qudt/applicableUnit', []).extend(list(diff))
                #print(self.qdict[self.qdict[q]['base_quantity'][0]]['http://qudt.org/schema/qudt/applicableUnit'])
        if not self.qdict[q]['http://qudt.org/schema/qudt/hasDimensionVector'][0] == self.qdict[self.qdict[q]['base_quantity'][0]]['http://qudt.org/schema/qudt/hasDimensionVector'][0]:
            print("WARNING: Different dim for subq {} and baseq {}".format(q, self.qdict[q]['base_quantity'][0]))
            
    def normUcumFracToLin(self, ucum):
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
            
    def set_wikidata_base_and_super_quantities(self, wId, ignore = []):
        w = self.wdict[wId]
        #print(json.dumps(q))
        base_quantity = []
        subquantity_of = []
        sup_base = []
        if 'http://www.wikidata.org/prop/P279' in w:
            for sup in w['http://www.wikidata.org/prop/P279']:
                if sup in ignore: continue
                if sup not in self.wdict: continue
                #print("{} -> {}".format(wId, sup))
                subquantity_of.append(sup)
                ignore.append(w) #prevent circular dep.
                sup_base.extend(self.set_wikidata_base_and_super_quantities(sup, ignore))
        if (len(sup_base) == 0): base_quantity.extend(subquantity_of)
        else: base_quantity.extend(sup_base)
        base_quantity = list(dict.fromkeys(base_quantity)) #remove duplicate
        self.wdict[wId]['base_quantity'] = base_quantity 
        self.wdict[wId]['subquantity_of'] = subquantity_of 
        if (len(base_quantity) > 1): print("WARNING: More than one base quantity for {}: {}".format(wId, base_quantity))
        return base_quantity

    def remove_wikidata_superclass(self, w, sup):
        if sup in self.wdict[w]['http://www.wikidata.org/prop/P279']: self.wdict[w]['http://www.wikidata.org/prop/P279'].remove(sup) 