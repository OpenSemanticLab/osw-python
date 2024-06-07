# 1: declare functions
# import json
# import os
# from SPARQLWrapper import SPARQLWrapper, POST, BASIC, JSON
# from pathlib import Path
# from utils import dict_to_json, json_to_dict
from SPARQLWrapper import SPARQLWrapper, POST, JSON
from pprint import pprint
from utils import dict_to_json
from collections import Counter


# call this class to fetch quantites
class QuantityFetcher:
    def __init__(self):
        print("\nfetching quantities...")
        self.fetchQuantities()
        print("\nquantities fetched\n")

    def sparqlQuery(self, endpoint, query):
        sparql = SPARQLWrapper(endpoint)
        sparql.setMethod(POST)
        # print(query)
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        # print(sparql.query())
        return sparql.query().convert()

    def get_sparql_triplets(
        self,
        endpoint,
        where_statement,
        select_statement="",
        inner_where_statement="?subject ?predicate ?object",
        tsubject="",
        tpredicate="",
        tobject="",
        limit=999999999,
    ):
        select_statement = ""
        if tsubject == "":
            select_statement += " ?subject"
        if tpredicate == "":
            select_statement += " ?predicate"
        if tobject == "":
            select_statement += " ?object"
        if tsubject != "":
            inner_where_statement = inner_where_statement.replace(
                "?subject", "<" + tsubject + ">"
            )
        if tpredicate != "":
            inner_where_statement = inner_where_statement.replace(
                "?predicate", "<" + tpredicate + ">"
            )
        if tobject != "":
            inner_where_statement = inner_where_statement.replace(
                "?object", "<" + tobject + ">"
            )
        query = (
            """
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
        """.replace(
                "{{{select_statement}}}", select_statement
            )
            .replace("{{{where_statement}}}", where_statement)
            .replace("{{{inner_where_statement}}}", inner_where_statement)
            .replace("{{{limit}}}", str(limit))
        )
        print(query)
        # select distinct ?p ?o where {<http://dbpedia.org/resource/Amount_of_substance> ?p ?o} LIMIT 100
        triples = self.sparqlQuery(endpoint, query)
        # print(triples)
        self.tdict = {}
        print("{} triplets found".format(len(triples["results"]["bindings"])))
        for t in triples["results"]["bindings"]:
            if tsubject == "":
                s = t["subject"]["value"]
            else:
                s = tsubject
            if tpredicate == "":
                p = t["predicate"]["value"]
            else:
                p = tpredicate
            if tobject == "":
                o = t["object"]["value"]
            else:
                o = tobject
            if "xml:lang" in t["object"]:
                o += "@" + t["object"]["xml:lang"]
            # print("{} {} {}".format(s,p,o))
            self.dict_append_tripl(self.tdict, s, p, o)
        # print(self.tdict)
        return self.tdict

    def get_sparql_wikidata_statement_triplets(
        self, endpoint, where_statement, limit=999999999
    ):
        select_statement = "?subject ?predicate ?spredicate ?object"
        inner_where_statement = "?subject ?predicate [?spredicate ?object; <http://wikiba.se/ontology#rank> ?rank]"
        query = (
            """
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
        """.replace(
                "{{{select_statement}}}", select_statement
            )
            .replace("{{{where_statement}}}", where_statement)
            .replace("{{{inner_where_statement}}}", inner_where_statement)
            .replace("{{{limit}}}", str(limit))
        )
        print(query)
        triples = self.sparqlQuery(endpoint, query)
        # print(triples)
        self.tdict = {}
        print("{} triplets found".format(len(triples["results"]["bindings"])))
        for t in triples["results"]["bindings"]:

            s = t["subject"]["value"]
            p = t["predicate"]["value"]
            sp = t["spredicate"]["value"]
            o = t["object"]["value"]
            if "xml:lang" in t["object"]:
                o += "@" + t["object"]["xml:lang"]
            # print("{} {}/{} {}".format(s,p,sp,o))
            if p.split("/")[-1] == sp.split("/")[-1]:
                self.dict_append_tripl(
                    self.tdict, s, p, o
                )  # e.g.  http://www.wikidata.org/prop/P2347 and http://www.wikidata.org/prop/statement/value-normalized/P2347
        # print(self.tdict)
        return self.tdict

    def qudtTypeQuery(self, qudt_type, limit=999999):  # doesn't work anymore
        sparql = SPARQLWrapper(
            "https://www.qudt.org/fuseki/qudt/sparql"
        )  # endpoint has changed from http to https
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
        """.replace(
            "{{{qudt_type}}}", qudt_type
        ).replace(
            "{{{limit}}}", str(limit)
        )
        # print(query)
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        # print(sparql.query())
        return sparql.query().convert()

    def dict_append_tripl(self, d, s, p, o):
        if s not in d:
            d[s] = {}
        if p not in d[s]:
            d[s][p] = []
        d[s][p].append(o)

    def getQudtTypeDict(self, qudt_type, limit=999999):
        triples = self.qudtTypeQuery(qudt_type, limit)
        self.tdict = {}
        for t in triples["results"]["bindings"]:
            s = t["subject"]["value"]
            p = t["predicate"]["value"]
            o = t["object"]["value"]
            if "xml:lang" in t["object"]:
                o += "@" + t["object"]["xml:lang"]
            # print("{} {} {}".format(s,p,o))
            self.dict_append_tripl(self.tdict, s, p, o)
        return self.tdict

    def print_subject_object(self, d, predicate_key):
        for s in d:
            print("{}: {}".format(s, d[s].get(predicate_key, "")))

    def getLangLabel(self, labels, lang):
        for label in labels:
            if "@" + lang in label:
                return label.replace("@" + lang, "")

    def fetchQuantities(self):
        limit = 999999999
        _qdict = self.getQudtTypeDict("QuantityKind", limit)
        _udict = self.getQudtTypeDict("Unit", limit)
        dSiDict = self.getQudtTypeDict("QuantityKindDimensionVector_SI", limit)
        dIsoDict = self.getQudtTypeDict(
            "QuantityKindDimensionVector_ISO", limit
        )
        dImpDict = self.getQudtTypeDict(
            "QuantityKindDimensionVector_Imperial", limit
        )
        dCgsDict = self.getQudtTypeDict(
            "QuantityKindDimensionVector_CGS", limit
        )
        _ddict = {**dImpDict, **dCgsDict, **dIsoDict, **dSiDict}  # merge dicts
        dict_to_json(_qdict, "_qdict")
        dict_to_json(_qdict, "qdict")  # copy
        dict_to_json(_udict, "_udict")
        dict_to_json(_udict, "udict")  # copy
        dict_to_json(dSiDict, "dSiDict")
        dict_to_json(dIsoDict, "dIsoDict")
        dict_to_json(dImpDict, "dImpDict")
        dict_to_json(dCgsDict, "dCgsDict")
        dict_to_json(_ddict, "_ddict")
        dict_to_json(_ddict, "ddict")  # copy
        # for q in qdict: print(q)
        # for u in udict: print(u)
        # for d in ddict: print(d)
        print(len(_qdict))
        print(len(_udict))
        print(len(_ddict))

        # wdict1 = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>+ <http://www.wikidata.org/entity/Q107715>.") #195656 triplets found
        # wdict2 = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P8393> ?qudtid.") #48411 triplets found
        # wdict = {**wdict1, **wdict2} #merge dicts, 3966 results
        wdict = self.get_sparql_triplets(
            "https://query.wikidata.org/sparql",
            "?subject <http://www.wikidata.org/prop/direct/P279>*/<http://www.wikidata.org/prop/direct/P8393> ?qudtid.",
        )  # quantities with qudt ref and their subq, 2484 results
        dict_to_json(wdict, "wdict")
        print(len(wdict))
        # only subquantities
        # wdict = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>/<http://www.wikidata.org/prop/direct/P279>+ <http://www.wikidata.org/entity/Q107715>.")
        # print(len(wdict))
        # wstdict1 = get_sparql_wikidata_statement_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>+ <http://www.wikidata.org/entity/Q107715>.") #get statement object, 131347 triplets
        # wstdict2 = get_sparql_wikidata_statement_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P8393> ?qudtid.") #get statement object, 37775 triplets
        # wstdict = {**wstdict1, **wstdict2} #merge dicts, 3966 results
        wstdict = self.get_sparql_wikidata_statement_triplets(
            "https://query.wikidata.org/sparql",
            "?subject <http://www.wikidata.org/prop/direct/P279>*/<http://www.wikidata.org/prop/direct/P8393> ?qudtid.",
        )  # get statement object
        dict_to_json(wstdict, "wstdict")
        print(len(wstdict))
        for st in wstdict:
            for p in wstdict[st]:
                o = wstdict[st][p]
                wdict[st][p] = o  # replace statement with object
        wudict1 = self.get_sparql_triplets(
            "https://query.wikidata.org/sparql",
            "?subject <http://www.wikidata.org/prop/direct/P31> <http://www.wikidata.org/entity/Q47574>.",
        )  # instance of unit of measurement: 1340 results
        wudict2 = self.get_sparql_triplets(
            "https://query.wikidata.org/sparql",
            "?subject <http://www.wikidata.org/prop/direct/P5061> ?symbol.",
        )  # has unit symbol: 2230 results
        wudict3 = self.get_sparql_triplets(
            "https://query.wikidata.org/sparql",
            "?quantity <http://www.wikidata.org/prop/P8111>/<http://www.wikidata.org/prop/statement/P8111> ?subject.",
        )  # is recommended unit of measurement of: 294 results
        wudict4 = self.get_sparql_triplets(
            "https://query.wikidata.org/sparql",
            "?subject <http://www.wikidata.org/prop/P111>/<http://www.wikidata.org/prop/statement/P111> ?quantity.",
        )  # has measured quantity: 3278 results
        wudict = {
            **wudict1,
            **wudict2,
            **wudict3,
            **wudict4,
        }  # merge dicts, 3966 results
        len(wudict)
        dict_to_json(wudict, "wudict")

        # dbpdict = get_sparql_triplets("https://dbpedia.org/sparql/", "?subject <http://purl.org/dc/terms/subject> <http://dbpedia.org/resource/Category:Physical_quantities>.", limit=11000)
        # dbpdict = get_sparql_triplets("https://dbpedia.org/sparql/", "?subject <http://purl.org/dc/terms/subject>/<http://www.w3.org/2004/02/skos/core#broader> <http://dbpedia.org/resource/Category:Quantity>.")
        # endpoint is limited to 10000 results so we have to restrict the request to the relevant property
        dbpdict = self.get_sparql_triplets(
            "https://dbpedia.org/sparql/",
            "?subject <http://purl.org/dc/terms/subject>/<http://www.w3.org/2004/02/skos/core#broader> <http://dbpedia.org/resource/Category:Quantity>.",
            tpredicate="http://www.w3.org/2002/07/owl#sameAs",
        )
        print(len(dbpdict))
        dict_to_json(dbpdict, "dbpdict")


class Quantities:
    def __init__(
        self,
        _ddict={},
        _qdict={},
        _udict={},
        dbpdict={},
        dCgsDict={},
        dImpDict={},
        dIsoDict={},
        dSiDict={},
        wdict={},
        wstdict={},
        wudict={},
    ):
        self._ddict = _ddict
        self._qdict = _qdict
        self._udict = _udict
        self.dbpdict = dbpdict
        self.dCgsDict = dCgsDict
        self.dImpDict = dImpDict
        self.dIsoDict = dIsoDict
        self.dSiDict = dSiDict
        self.wdict = wdict
        self.wstdict = wstdict
        self.wudict = wudict
        self.ddict = _ddict.copy()
        self.qdict = _qdict.copy()
        self.udict = _udict.copy()

    def remove_wikidata_superclass(self, w, sup):
        if sup in self.wdict[w]["http://www.wikidata.org/prop/P279"]:
            self.wdict[w]["http://www.wikidata.org/prop/P279"].remove(sup)
            print("remove_wikidata_superclass: ", sup)

    def set_wikidata_base_and_super_quantities(self, wId, ignore=[]):
        w = self.wdict[wId]
        # print(json.dumps(q))
        base_quantity = []
        subquantity_of = []
        sup_base = []
        if "http://www.wikidata.org/prop/P279" in w:
            for sup in w["http://www.wikidata.org/prop/P279"]:
                if sup in ignore:
                    continue
                if sup not in self.wdict:
                    continue
                # print("{} -> {}".format(wId, sup))
                subquantity_of.append(sup)
                ignore.append(w)  # prevent circular dep.
                sup_base.extend(
                    self.set_wikidata_base_and_super_quantities(sup, ignore)
                )
        if len(sup_base) == 0:
            base_quantity.extend(subquantity_of)
        else:
            base_quantity.extend(sup_base)
        base_quantity = list(dict.fromkeys(base_quantity))  # remove duplicate
        self.wdict[wId]["base_quantity"] = base_quantity
        self.wdict[wId]["subquantity_of"] = subquantity_of
        if len(base_quantity) > 1:
            print(
                "WARNING: More than one base quantity for {}: {}".format(
                    wId, base_quantity
                )
            )
        return base_quantity

    def normUcumFracToLin(self, ucum):
        result = ""
        fraction = False
        index = 0
        for c in ucum:  # iterate over all chars
            skip = False
            if c == "/":
                fraction = True
                if index > 0:
                    result += (
                        "."  # some ucums begin with a '/', no sep '.' needed
                    )
                skip = True
            if fraction:
                if c == "." and ucum[index - 1] not in [
                    "0",
                    "1",
                    "2",
                    "3",
                    "4",
                    "5",
                    "6",
                    "7",
                    "8",
                    "9",
                ]:  # exponent 1 is implicit, e.g. 'm.' -> 'm1.'
                    result += "-1"  # assume 1 and invert it to -1
                if c == "(":
                    skip = True
                elif c == ")":
                    skip = True
                    if index != len(ucum) - 1:
                        print(
                            "Error: closing bracket not last char in {}".format(
                                ucum
                            )
                        )
                        return ucum
                elif c == "-":
                    skip = True  # make it positiv anyway
                    print(
                        "Warning: negativ exponent in fraction in {}".format(
                            ucum
                        )
                    )
                elif c in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                    if ucum[index - 1] in [
                        "0",
                        "1",
                        "2",
                        "3",
                        "4",
                        "5",
                        "6",
                        "7",
                        "8",
                        "9",
                    ]:  # Todo: ignore factors like '/100cm2'
                        print("Error: double number in {}".format(ucum))
                        return ucum
                    result += "-"  # e.g. 's2' -> 's-2'
                if not skip:
                    result += c
            else:
                result += c
            if not fraction and (c == "(" or c == ")"):
                print("Error: brackets without fraktion in {}".format(ucum))
                return ucum
            index += 1
        if fraction and result[-1] not in [
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
        ]:
            result += "-1"  # e.g. '/m': exponent 1 is implicit -> '/m-1'
        # if ucum != result: print("Normalize '{}' to '{}'".format(ucum, result))
        return result

    # nomalize_ucum("kg/(m.s2)")

    def analyzeWikidata(self):
        print("\nanalyzing wikidata...")
        w_base_q = []
        no_unit = []
        no_dim = []
        for w in self.wdict:
            # if 'http://www.wikidata.org/entity/Q107715' in wdict[w]['http://www.wikidata.org/prop/direct/P279']:
            #    w_base_q.append(w)
            sub_q = False
            for sup in self.wdict[w][
                "http://www.wikidata.org/prop/direct/P279"
            ]:
                if sup in self.wdict:
                    sub_q = True
                    break
            if not sub_q:
                w_base_q.append(w)
            if (
                "http://www.wikidata.org/prop/direct/P4020"
                not in self.wdict[w]
            ):
                no_dim.append(w)
            else:
                if (
                    "http://www.wikidata.org/prop/direct/P8111"
                    not in self.wdict[w]
                    and self.wdict[w][
                        "http://www.wikidata.org/prop/direct/P4020"
                    ]
                    != "1"
                ):
                    no_unit.append(w)

        print("w_base_q: ", len(w_base_q))
        print("no_unit: ", len(no_unit))
        print("no_dim: ", len(no_dim))
        # for w in w_base_q:
        #    print(getLangLabel(wdict[w]["http://www.w3.org/2000/01/rdf-schema#label"], 'en'))
        ignore_list = []
        ignore_list.append(
            "http://www.wikidata.org/entity/Q181175"
        )  # scalar quantity
        ignore_list.append(
            "http://www.wikidata.org/entity/Q2672914"
        )  # vector quantity
        self.remove_wikidata_superclass(
            "http://www.wikidata.org/entity/Q589446",
            "http://www.wikidata.org/entity/Q3686031",
        )  # mass concentration is not subclass of amount concentration
        self.remove_wikidata_superclass(
            "http://www.wikidata.org/entity/Q76378758",
            "http://www.wikidata.org/entity/Q3686031",
        )  # mass concentration of water is not subclass of amount concentration
        self.remove_wikidata_superclass(
            "http://www.wikidata.org/entity/Q13824",
            "http://www.wikidata.org/entity/Q11465",
        )  # phase speed is not a velocity
        self.remove_wikidata_superclass(
            "http://www.wikidata.org/entity/Q86508881",
            "http://www.wikidata.org/entity/Q11465",
        )  # sound speed is not a velocity
        self.remove_wikidata_superclass(
            "http://www.wikidata.org/entity/Q86508881",
            "http://www.wikidata.org/entity/Q217361",
        )  # sound speed is not a group velocity Q217361
        self.remove_wikidata_superclass(
            "http://www.wikidata.org/entity/Q1097654",
            "http://www.wikidata.org/entity/Q11379",
        )  # rest mass is not an energy
        self.remove_wikidata_superclass(
            "http://www.wikidata.org/entity/Q4128476",
            "http://www.wikidata.org/entity/Q25288",
        )  # birth weight is a mass, not a force
        self.remove_wikidata_superclass(
            "http://www.wikidata.org/entity/Q6795900",
            "http://www.wikidata.org/entity/Q25288",
        )  # landing weight is a mass, not a force
        self.remove_wikidata_superclass(
            "http://www.wikidata.org/entity/Q6795910",
            "http://www.wikidata.org/entity/Q25288",
        )  # maximum ramp weight is a mass, not a force
        self.remove_wikidata_superclass(
            "http://www.wikidata.org/entity/Q16815754",
            "http://www.wikidata.org/entity/Q25288",
        )  # operating weight is a mass, not a force
        self.remove_wikidata_superclass(
            "http://www.wikidata.org/entity/Q55435676",
            "http://www.wikidata.org/entity/Q275157",
        )  # fasting serum glucose level is a mass concentration, blood glucose is a amount concentration
        ignore_list.append(
            "http://www.wikidata.org/entity/Q111811675"
        )  # area dublicate
        self.remove_wikidata_superclass(
            "http://www.wikidata.org/entity/Q11500",
            "http://www.wikidata.org/entity/Q111811675",
        )  # area is not subclass of dublicated area class (recursion)
        counter = 0
        for w in self.wdict:
            self.set_wikidata_base_and_super_quantities(w, ignore_list)
            counter += 1

        print(
            "set_wikidata_base_and_super_quantities counter: ", counter, "\n"
        )

    def dbpediaToWikidata(self):
        self.dbpwdict = {}
        for dbp in self.dbpdict:
            w = ""
            for uri in self.dbpdict[dbp].get(
                "http://www.w3.org/2002/07/owl#sameAs", []
            ):
                if "wikidata.org/entity/" in uri:
                    w = uri
                    break
            self.dbpwdict[dbp] = w

        print(
            "length self.dbpwdict: ", len(self.dbpwdict)
        )  # § create json instead of print

        # create dict qudt -> wikidata
        self.qwdict = {}
        for w in self.wdict:
            if (
                "http://www.wikidata.org/prop/direct-normalized/P8393"
                in self.wdict[w]
            ):
                self.qwdict[
                    self.wdict[w][
                        "http://www.wikidata.org/prop/direct-normalized/P8393"
                    ][0]
                ] = w
        print(len(self.qwdict))
        self.qdbpdict = {}
        for q in self.qdict:
            if "http://qudt.org/schema/qudt/dbpediaMatch" in self.qdict[q]:
                dbp = self.qdict[q][
                    "http://qudt.org/schema/qudt/dbpediaMatch"
                ][0]
                w = self.qwdict.get(q, "")
                if (
                    self.dbpwdict.get(dbp, "") != ""
                    and self.dbpwdict.get(dbp, "") != w
                ):
                    print(
                        "Wikidata Uri diff for {} and {}: {} vs {}".format(
                            q, dbp, w, self.dbpwdict.get(dbp, "")
                        )
                    )
                    self.qwdict[q] = self.dbpwdict[dbp]
                self.qdbpdict[q] = dbp
        # print(len(self.qdbpdict))
        print("length self.qwdict before: ", len(self.qwdict))
        for q in self._qdict:
            if "http://qudt.org/schema/qudt/dbpediaMatch" in self._qdict[q]:
                dbp = self._qdict[q][
                    "http://qudt.org/schema/qudt/dbpediaMatch"
                ][0]
                w = self.qwdict.get(q, "")
                if (
                    self.dbpwdict.get(dbp, "") != ""
                    and self.dbpwdict.get(dbp, "") != w
                ):
                    print(
                        "Wikidata Uri diff for {} and {}: {} vs {}".format(
                            q, dbp, w, self.dbpwdict.get(dbp, "")
                        )
                    )
                    if q not in self.qwdict:
                        print("add " + q)
                        self.qwdict[q] = self.dbpwdict[dbp]
                self.qdbpdict[q] = dbp
        print(
            "length self.qwdict after: ", len(self.qwdict)
        )  # 5 quantities have missing units or dimension in qudt but are defined in wikidata

        self.ucum_u_dict = {}  # ucum to qudt unit
        for u in self.udict:
            if "http://qudt.org/schema/qudt/ucumCode" in self.udict[u]:
                if (
                    self.udict[u]["http://qudt.org/schema/qudt/ucumCode"][0]
                    in self.ucum_u_dict
                ):
                    ucum = self.udict[u][
                        "http://qudt.org/schema/qudt/ucumCode"
                    ][0]
                    print(
                        "Warning: Conflict for {}: {} vs {}".format(
                            ucum, u, self.ucum_u_dict[ucum]
                        )
                    )
                self.ucum_u_dict[
                    self.udict[u]["http://qudt.org/schema/qudt/ucumCode"][0]
                ] = u
        print(len(self.udict))
        print(len(self.ucum_u_dict))
        # uwudict = {} # qudt unit to wiki data unit
        self.ucum_wu_dict = {}  # ucum to wikidata unit
        for wu in self.wudict:
            if (
                "http://www.wikidata.org/prop/direct/P7825" in self.wudict[wu]
            ):  # and 'http://www.wikidata.org/prop/direct/P5061' in self.wudict[wu]:
                # print(self.wudict[wu]['http://www.wikidata.org/prop/direct/P5061'])
                for ucum in self.wudict[wu][
                    "http://www.wikidata.org/prop/direct/P7825"
                ]:
                    self.ucum_wu_dict[self.normUcumFracToLin(ucum)] = wu
        print(len(self.ucum_wu_dict))

    def set_base_and_super_quantities(self, qId, ignore=[]):
        q = self.qdict[qId]
        # print(json.dumps(q))
        base_quantity = []
        subquantity_of = []
        if "http://www.w3.org/2004/02/skos/core#broader" in q:
            for sup in q["http://www.w3.org/2004/02/skos/core#broader"]:
                if sup in ignore:
                    continue
                # print(sup)
                subquantity_of.append(sup)
                # has_super = True
                # while('http://www.w3.org/2004/02/skos/core#broader' in self.qdict[sup]):
                #    sup = self.qdict[sup]['http://www.w3.org/2004/02/skos/core#broader'][0]
                #    print("-> " + sup)
                sup_base = self.set_base_and_super_quantities(sup, ignore)
                if len(sup_base) == 0:
                    base_quantity.extend(subquantity_of)
                else:
                    base_quantity.extend(sup_base)
        self.qdict[qId]["base_quantity"] = base_quantity
        self.qdict[qId]["subquantity_of"] = subquantity_of
        if len(base_quantity) > 1:
            print("WARNING: More than one base quantity for " + str(qId))
        return base_quantity

    def set_main_and_invalid_units(self, qId):
        q = self.qdict[qId]
        # print(json.dumps(q))
        main_units = []
        invalid_units = []
        units_by_conversion_factor = {}
        if (
            "http://qudt.org/schema/qudt/applicableUnit" in q
            and not isinstance(
                q["http://qudt.org/schema/qudt/applicableUnit"], type(None)
            )
        ):
            for u in q["http://qudt.org/schema/qudt/applicableUnit"]:
                # print(self.udict[u])
                if (
                    "http://qudt.org/schema/qudt/conversionMultiplier"
                    in self.udict[u]
                ):
                    cf = self.udict[u][
                        "http://qudt.org/schema/qudt/conversionMultiplier"
                    ][0]
                    if float(cf) not in units_by_conversion_factor:
                        units_by_conversion_factor[float(cf)] = []
                    units_by_conversion_factor[float(cf)].append(u)
                    if float(cf) == 1.0:
                        main_units.append(u)
                    elif float(cf) == 0.0:
                        invalid_units.append(u)
                else:
                    invalid_units.append(u)
                # print("{}: {}".format(u, cf))
        self.qdict[qId]["main_units"] = main_units
        self.qdict[qId]["invalid_units"] = invalid_units
        self.qdict[qId]["units_by_conversion_factor"] = dict(
            sorted(units_by_conversion_factor.items())
        )
        # print("{}: mu:{} iu:{}".format(qId, main_units, invalid_units))

    def validate_base_unit(self, q):
        units = []
        base_units = []
        # if not 'base_quantity' in self.qdict[q]: return True
        if len(self.qdict[q]["base_quantity"]) == 0:
            return True
        units.extend(
            self.qdict[q].get("http://qudt.org/schema/qudt/applicableUnit", [])
        )
        # print(self.qdict[q]['base_quantity'])
        base_units.extend(
            self.qdict[self.qdict[q]["base_quantity"][0]].get(
                "http://qudt.org/schema/qudt/applicableUnit", []
            )
        )
        sym_diff = set(units).symmetric_difference(set(base_units))
        if not len(sym_diff) == 0:
            # print("WARNING: Different units for subq {} ({}) and baseq {} ({})".format(q, len(units), self.qdict[q]['base_quantity'][0], len(base_units)))
            if len(units) > len(base_units):
                print(
                    "WARNING: More units for subq {} than baseq {}".format(
                        q, self.qdict[q]["base_quantity"][0]
                    )
                )
                diff = set(units).difference(set(base_units))
                print(diff)
                # print(self.qdict[self.qdict[q]['base_quantity'][0]]['http://qudt.org/schema/qudt/applicableUnit'])
                if (
                    "http://qudt.org/schema/qudt/applicableUnit"
                    in self.qdict[self.qdict[q]["base_quantity"][0]]
                ):
                    self.qdict[self.qdict[q]["base_quantity"][0]][
                        "http://qudt.org/schema/qudt/applicableUnit"
                    ].extend(list(diff))
                else:
                    self.qdict[self.qdict[q]["base_quantity"][0]][
                        "http://qudt.org/schema/qudt/applicableUnit"
                    ] = list(diff)
                # self.qdict[self.qdict[q]['base_quantity'][0]]['http://qudt.org/schema/qudt/applicableUnit'] = self.qdict[self.qdict[q]['base_quantity'][0]].get('http://qudt.org/schema/qudt/applicableUnit', []).extend(list(diff))
                # print(self.qdict[self.qdict[q]['base_quantity'][0]]['http://qudt.org/schema/qudt/applicableUnit'])
        if (
            not self.qdict[q][
                "http://qudt.org/schema/qudt/hasDimensionVector"
            ][0]
            == self.qdict[self.qdict[q]["base_quantity"][0]][
                "http://qudt.org/schema/qudt/hasDimensionVector"
            ][0]
        ):
            print(
                "WARNING: Different dim for subq {} and baseq {}".format(
                    q, self.qdict[q]["base_quantity"][0]
                )
            )

    def mergeQudtAndWikidata(self):
        for q in self.qdict:
            if "http://qudt.org/schema/qudt/applicableUnit" in self.qdict[
                q
            ] and isinstance(
                self.qdict[q]["http://qudt.org/schema/qudt/applicableUnit"],
                type(None),
            ):
                self.qdict[q][
                    "http://qudt.org/schema/qudt/applicableUnit"
                ] = []

        remove_list = []
        for q in self.qdict:
            invalid = False
            if (
                "http://qudt.org/schema/qudt/hasDimensionVector"
                not in self.qdict[q]
            ):
                # print("Invalid (no dim): " + q)
                invalid = True
            if invalid:
                remove_list.append(q)

        # manual corrections
        remove_list.append(
            "http://qudt.org/vocab/quantitykind/ElectricField"
        )  # dublicate of http://qudt.org/vocab/quantitykind/ElectricFieldStrength
        remove_list.append("http://qudt.org/vocab/quantitykind/InverseTime")
        for q in remove_list:
            del self.qdict[q]
        if (
            "http://qudt.org/vocab/quantitykind/InformationFlowRate"
            in self.qdict["http://qudt.org/vocab/quantitykind/DataRate"][
                "http://www.w3.org/2004/02/skos/core#broader"
            ]
        ):
            self.qdict["http://qudt.org/vocab/quantitykind/DataRate"][
                "http://www.w3.org/2004/02/skos/core#broader"
            ].remove(
                "http://qudt.org/vocab/quantitykind/InformationFlowRate"
            )  # invalid super quantity
        self.qdict["http://qudt.org/vocab/quantitykind/MassFraction"][
            "http://www.w3.org/2004/02/skos/core#broader"
        ] = ["http://qudt.org/vocab/quantitykind/DimensionlessRatio"]
        self.qdict["http://qudt.org/vocab/quantitykind/MassFractionOfWater"][
            "http://www.w3.org/2004/02/skos/core#broader"
        ] = ["http://qudt.org/vocab/quantitykind/MassFraction"]

        self.udict["http://qudt.org/vocab/unit/UNITLESS"][
            "http://qudt.org/schema/qudt/ucumCode"
        ] = ["[1]"]
        self.udict["http://qudt.org/vocab/unit/PERCENT"][
            "http://qudt.org/schema/qudt/conversionMultiplier"
        ] = ["0.01"]

        for q in self.qdict:
            # print(q)
            self.set_main_and_invalid_units(q)
            self.set_base_and_super_quantities(q, remove_list)

        # retrieve hierarchy from wikidata
        self.qwdict_inv = {v: k for k, v in self.qwdict.items()}
        for q in self.qdict:
            if len(self.qdict[q]["base_quantity"]) > 0:
                sup = self.qdict[q]["base_quantity"][0]
            else:
                sup = ""
            if q in self.qwdict:
                w = self.qwdict[q]
                if w in self.wdict:
                    if len(self.wdict[w]["base_quantity"]) > 0:
                        wsup = self.wdict[w]["base_quantity"][0]
                    else:
                        wsup = ""
                    if wsup in self.qwdict_inv:
                        wsup_q = self.qwdict_inv[wsup]
                        if sup != wsup_q:
                            if sup == "":
                                # print("new base_quantity {} for {}".format(wsup_q, q))
                                if wsup_q in self.qdict:
                                    self.qdict[q]["base_quantity"] = [wsup_q]
                                    self.qdict[q]["subquantity_of"] = [wsup_q]
                                # i = 1
                            elif (
                                wsup_q in self.qdict
                                and sup in self.qdict[wsup_q]["base_quantity"]
                            ):
                                print(
                                    "Resolveable Diff {} <-> {} for {}".format(
                                        sup, wsup_q, q
                                    )
                                )
                                # i = 1
                            else:
                                print(
                                    "Unresolveable Diff {} <-> {} for {}".format(
                                        sup, wsup_q, q
                                    )
                                )
                        # else: print("No diff {} {}".format(sup, wsup_q))
                    # print("Missing in inv: {}".format(wsup))
                else:
                    print("Missing: {}".format(w))
        # manual corrections failed
        # self.qdict['http://qudt.org/vocab/quantitykind/DynamicViscosity']['base_quantity'].remove('http://qudt.org/vocab/quantitykind/Force')
        # self.qdict['http://qudt.org/vocab/quantitykind/DynamicViscosity']['subquantity_of'].remove('http://qudt.org/vocab/quantitykind/Force')

        for q in self.qdict:
            # print(q)
            self.set_main_and_invalid_units(q)
            self.validate_base_unit(q)

        remove_list = []
        for q in self.qdict:
            invalid = False
            if (
                "http://qudt.org/schema/qudt/applicableUnit"
                not in self.qdict[q]
            ):
                print("Invalid (no units): " + q)
                invalid = True
            if invalid:
                remove_list.append(q)

        for q in remove_list:
            del self.qdict[q]

        for q in self.qdict:
            self.validate_base_unit(q)

        broader_cluster = []
        dim_cluster = []
        for q in self.qdict:
            if len(self.qdict[q]["base_quantity"]) > 0:
                broader_cluster.append(self.qdict[q]["base_quantity"][0])
            else:
                broader_cluster.append(q)
            dim_cluster.append(
                self.qdict[q][
                    "http://qudt.org/schema/qudt/hasDimensionVector"
                ][0]
            )

        self.bres = Counter(broader_cluster)
        self.bres = {
            k: v
            for k, v in sorted(
                self.bres.items(), key=lambda item: item[1], reverse=True
            )
        }
        self.dres = Counter(dim_cluster)
        self.dres = {
            k: v
            for k, v in sorted(
                self.dres.items(), key=lambda item: item[1], reverse=True
            )
        }
        self.stats = {}
        for dim in self.dres:
            self.stats[dim] = {
                "total": self.dres[dim],
                "broader_cluster_member_count": 0,
                "broader_cluster": {},
            }
        for q in self.bres:
            d = self.qdict[q][
                "http://qudt.org/schema/qudt/hasDimensionVector"
            ][0]
            self.stats[d]["broader_cluster"][q] = {
                "member_count": self.bres[q]
            }
            self.stats[d]["broader_cluster_member_count"] += self.bres[q]
        # print(self.stats)

        for q in self.qdict:
            if (
                "http://qudt.org/vocab/dimensionvector/A0E0L3I0M0H0T0D0"
                in self.qdict[q][
                    "http://qudt.org/schema/qudt/hasDimensionVector"
                ]
            ):
                print(q)

    def get_property_wiki_page_name(self, uri):
        return "Property:Has" + uri.split("/")[-1]

    def get_description(self, q):
        text = ""
        if "http://purl.org/dc/terms/description" in self.qdict[q]:
            text += self.qdict[q]["http://purl.org/dc/terms/description"][0]
        if "http://qudt.org/schema/qudt/plainTextDescription" in self.qdict[q]:
            text += (
                "\n=== Plain text ===\n"
                + self.qdict[q][
                    "http://qudt.org/schema/qudt/plainTextDescription"
                ][0]
            )
        if "http://qudt.org/schema/qudt/latexDefinition" in self.qdict[q]:
            text += (
                "\n=== Latex ===\n"
                + self.qdict[q]["http://qudt.org/schema/qudt/latexDefinition"][
                    0
                ]
            )
        text = (
            text.replace("\\(", "<math>")
            .replace("\\)", "</math>")
            .replace("\\", "\\")
        )
        return text

    def get_wikipage_dict(self, q):
        wt = {
            "title": self.get_property_wiki_page_name(q),
            "content": [{"OslTemplate:Property/Quantity": {}}],
        }
        wtq = wt["content"][0]["OslTemplate:Property/Quantity"]
        wtq["label"] = self.qdict[q][
            "http://www.w3.org/2000/01/rdf-schema#label"
        ][0]
        if (
            q in self.qwdict
            and "http://www.w3.org/2000/01/rdf-schema#label"
            in self.wdict[self.qwdict[q]]
        ):
            # wtq['label_de'] = getLangLabel(self.wdict[self.qwdict[q]]['http://www.w3.org/2000/01/rdf-schema#label'], 'de')
            wtq["label"] = self.wdict[self.qwdict[q]][
                "http://www.w3.org/2000/01/rdf-schema#label"
            ]
            for label in wtq["label"]:
                if any(
                    substring in label
                    for substring in ["@zh-cn", "@ms-arab", "@sms", "@smj"]
                ):
                    wtq["label"].remove(label)  # unsupported
        else:
            wtq["label"] = (
                self.qdict[q]["http://www.w3.org/2000/01/rdf-schema#label"][0]
                + "@en"
            )
        wtq["ontology_iri"] = [q]
        if q in self.qwdict:
            wtq["ontology_iri"].append(self.qwdict[q])
        if q in self.qdbpdict:
            wtq["ontology_iri"].append(self.qdbpdict[q])
        wtq["description"] = self.get_description(q)
        if len(self.qdict[q]["base_quantity"]) == 0:
            wtq["main_unit"] = ""
            wtq["alternative_names"] = []
            wtq["main_unit_ontology_iri"] = []
            wtq["alternative_units"] = []
            units = []
            unit_uris = []
            for cf in self.qdict[q]["units_by_conversion_factor"]:
                wtu = {
                    "alternative_names": [],
                    "ontology_iri": [],
                    "use_as_display_unit": "Yes",
                    "use_as_input_unit": "Yes",
                }
                valid = False
                first = True
                for index, u in enumerate(
                    self.qdict[q]["units_by_conversion_factor"][cf]
                ):
                    # print(u)
                    unit_uris.append(u)
                    if (
                        "http://qudt.org/schema/qudt/ucumCode"
                        not in self.udict[u]
                    ):
                        print(
                            "Warning: Unit {} without ucum code ignored".format(
                                u
                            )
                        )
                        continue
                    ucum = self.udict[u][
                        "http://qudt.org/schema/qudt/ucumCode"
                    ][0]
                    if "{" in ucum:
                        print(
                            "Warning: Unit {} without invalid char ignored".format(
                                u
                            )
                        )
                        continue
                    sym = ucum
                    if "[" in sym:
                        print(
                            "Warning: Imperial Unit {} only for reference".format(
                                u
                            )
                        )
                        wtu["use_as_display_unit"] = "No"
                        wtu["use_as_input_unit"] = "No"
                    # if ucum in ucum_wu_dict:
                    #    if 'http://www.wikidata.org/prop/direct/P5061' in wudict[ucum_wu_dict[ucum]]:
                    #        sym = getLangLabel(wudict[ucum_wu_dict[ucum]]['http://www.wikidata.org/prop/direct/P5061'],'en')
                    #    unit_uris.append(ucum_wu_dict[ucum])
                    # else: print("Not found: {}".format(ucum))
                    units.append(sym)
                    if cf == 1.0:
                        if first:
                            wtq["main_unit"] = sym
                            first = False
                        else:
                            if len(sym) < len(
                                wtq["main_unit"]
                            ):  # policy: use shortes ucum as main symbol
                                wtq["alternative_names"].append(
                                    wtq["main_unit"]
                                )
                                wtq["main_unit"] = sym
                            else:
                                wtq["alternative_names"].append(sym)
                        wtq["main_unit_ontology_iri"].append(u)
                    if cf != 1.0:
                        wtu["factor"] = str(
                            1.0 / cf
                        )  # Semantic Mediawiki uses inverse conversion factor
                        if first:
                            wtu["unit"] = sym
                            first = False
                        else:
                            if len(sym) < len(
                                wtu["unit"]
                            ):  # policy: use shortes ucum as main symbol
                                wtu["alternative_names"].append(wtu["unit"])
                                wtu["unit"] = sym
                            else:
                                wtu["alternative_names"].append(sym)
                        wtu["ontology_iri"].append(u)
                    valid = True
                if cf != 1.0 and valid:
                    wtq["alternative_units"].append(
                        {"OslTemplate:Property/Quantity/Unit": wtu}
                    )
        else:
            wtq["base_quantity"] = self.get_property_wiki_page_name(
                self.qdict[q]["base_quantity"][0]
            )
            wtq["subquantity_of"] = []
            for sup in self.qdict[q]["subquantity_of"]:
                wtq["subquantity_of"].append(
                    self.get_property_wiki_page_name(sup)
                )
            wtq["display_units"] = []
            wtq["input_units"] = []
            for cf in self.qdict[q]["units_by_conversion_factor"]:
                for index, u in enumerate(
                    self.qdict[q]["units_by_conversion_factor"][cf]
                ):
                    if (
                        "http://qudt.org/schema/qudt/ucumCode"
                        not in self.udict[u]
                    ):
                        print(
                            "Warning: Unit {} without ucum code ignored".format(
                                u
                            )
                        )
                        continue
                    ucum = self.udict[u][
                        "http://qudt.org/schema/qudt/ucumCode"
                    ][0]
                    sym = ucum
                    if "[" in sym:
                        print("Warning: Imperial Unit {} ignored".format(u))
                        continue
                    wtq["display_units"].append(sym)
                    wtq["input_units"].append(sym)
        return wt

    def get_wikitext_from_wikipage_dict(self, d):
        wt = ""
        for key, value in d.items():
            # print("key: {}, valuetype: {}, value: {}".format(key, type(value), ""))
            if isinstance(value, dict):
                # print("dict")
                wt += "\n{{" + key
                wt += self.get_wikitext_from_wikipage_dict(value)
                wt += "\n}}"
            elif isinstance(value, list):
                # print("list")
                wt += "\n|{}=".format(key)
                for index, element in enumerate(value):
                    if isinstance(element, dict):
                        wt += self.get_wikitext_from_wikipage_dict(element)
                        # wt += "\n{{" + element
                        # wt += get_wikitext_from_dict(element)
                        # wt += "\n}}"
                    else:
                        if index > 0:
                            wt += ";"
                        wt += element
            else:
                # print("literal")
                wt += "\n|{}={}".format(key, value)
        return wt

    def set_wikitext_from_content(self, p):
        wt = ""
        for content_element in p["content"]:
            if isinstance(content_element, dict):
                wt += self.get_wikitext_from_wikipage_dict(content_element)
            elif isinstance(content_element, str):
                wt += "\n" + content_element
            else:
                print(
                    "Error: content element is not dict or string: {}".format(
                        content_element
                    )
                )
        p["wikitext"] = wt
        return wt

    def create_wiki_code(self):
        q_list = []
        # q_list.append('http://qudt.org/vocab/quantitykind/AmbientPressure')
        # q_list.append('http://qudt.org/vocab/quantitykind/Pressure')
        # q_list.append('http://qudt.org/vocab/quantitykind/ForcePerArea')
        # q_list.append('http://qudt.org/vocab/quantitykind/Time')
        # q_list.append('http://qudt.org/vocab/quantitykind/Temperature')
        q_list.append("http://qudt.org/vocab/quantitykind/Temperature")
        # q_list.append('http://qudt.org/vocab/quantitykind/Force')
        # q_list.append('http://qudt.org/vocab/quantitykind/Stress')
        # q_list.append('http://qudt.org/vocab/quantitykind/ShearStress')
        # q_list.append('http://qudt.org/vocab/quantitykind/NormalStress')
        # q_list.append('http://qudt.org/vocab/quantitykind/DimensionlessRatio')
        # q_list.append('http://qudt.org/vocab/quantitykind/MoleFraction')
        # q_list.append('http://qudt.org/vocab/quantitykind/LiquidVolume')
        # q_list.append('http://qudt.org/vocab/quantitykind/Volume')
        pages = []
        for q in q_list:
            p = self.get_wikipage_dict(q)
            pprint(p)  # json.dumps(p))
            # wiki_text = self.set_wikitext_from_content(p)
            # print(wiki_text)
            pages.append(p)
