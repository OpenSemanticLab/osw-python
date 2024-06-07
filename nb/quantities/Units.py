#!/usr/bin/env python
# coding: utf-8

# # ToDo
# 1. [x] Validate normalize ucum
# 2. [x] Inverse normalize
#         'kg.m-1.s-2' -> 'kg/(m.s2)'
# 3. [x] Validate inverse normalize
# 4. [] Create Ucum-Mapping-Dictionary
# 5. [] Nice-to-have: 'render' ucum
#         e. g. 'kg/(m s²) or '<math>\frac{kg}{ms^2}</math>'

# ## Function definitions


from SPARQLWrapper import SPARQLWrapper, POST, JSON

# from SPARQLWrapper import SPARQLWrapper, POST, BASIC, JSON


def sparqlQuery(endpoint, query):
    sparql = SPARQLWrapper(endpoint)
    sparql.setMethod(POST)
    # print(query)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    # print(sparql.query())
    return sparql.query().convert()


def get_sparql_triplets(
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
    triples = sparqlQuery(endpoint, query)
    # print(triples)
    tdict = {}
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
        dict_append_tripl(tdict, s, p, o)
    # print(tdict)
    return tdict


def get_sparql_wikidata_statement_triplets(
    endpoint, where_statement, limit=999999999
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
    triples = sparqlQuery(endpoint, query)
    # print(triples)
    tdict = {}
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
            dict_append_tripl(
                tdict, s, p, o
            )  # e.g.  http://www.wikidata.org/prop/P2347 and http://www.wikidata.org/prop/statement/value-normalized/P2347
    # print(tdict)
    return tdict


def qudtTypeQuery(qudt_type, limit=999999):
    sparql = SPARQLWrapper("https://www.qudt.org/fuseki/qudt/sparql")
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


def dict_append_tripl(d, s, p, o):
    if s not in d:
        d[s] = {}
    if p not in d[s]:
        d[s][p] = []
    d[s][p].append(o)


def getQudtTypeDict(qudt_type, limit=999999):
    triples = qudtTypeQuery(qudt_type, limit)
    tdict = {}
    for t in triples["results"]["bindings"]:
        s = t["subject"]["value"]
        p = t["predicate"]["value"]
        o = t["object"]["value"]
        if "xml:lang" in t["object"]:
            o += "@" + t["object"]["xml:lang"]
        # print("{} {} {}".format(s,p,o))
        dict_append_tripl(tdict, s, p, o)
    return tdict


def print_subject_object(d, predicate_key):
    for s in d:
        print("{}: {}".format(s, d[s].get(predicate_key, "")))


# ## Get data

# In[2]:


limit = 999999999
qdict = getQudtTypeDict("QuantityKind", limit)
udict = getQudtTypeDict("Unit", limit)
dSiDict = getQudtTypeDict("QuantityKindDimensionVector_SI", limit)
dIsoDict = getQudtTypeDict("QuantityKindDimensionVector_ISO", limit)
dImpDict = getQudtTypeDict("QuantityKindDimensionVector_Imperial", limit)
dCgsDict = getQudtTypeDict("QuantityKindDimensionVector_CGS", limit)
ddict = {**dImpDict, **dCgsDict, **dIsoDict, **dSiDict}  # merge dicts
# for q in qdict: print(q)
# for u in udict: print(u)
# for d in ddict: print(d)
print(len(qdict))
print(len(udict))
print(len(ddict))

# wdict1 = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>+ <http://www.wikidata.org/entity/Q107715>.") #195656 triplets found
# wdict2 = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P8393> ?qudtid.") #48411 triplets found
# wdict = {**wdict1, **wdict2} #merge dicts, 3966 results
wdict = get_sparql_triplets(
    "https://query.wikidata.org/sparql",
    "?subject <http://www.wikidata.org/prop/direct/P279>*/<http://www.wikidata.org/prop/direct/P8393> ?qudtid.",
)  # quantities with qudt ref and their subq, 2484 results
print(len(wdict))
# only subquantities
# wdict = get_sparql_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>/<http://www.wikidata.org/prop/direct/P279>+ <http://www.wikidata.org/entity/Q107715>.")
# print(len(wdict))
# wstdict1 = get_sparql_wikidata_statement_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P279>+ <http://www.wikidata.org/entity/Q107715>.") #get statement object, 131347 triplets
# wstdict2 = get_sparql_wikidata_statement_triplets("https://query.wikidata.org/sparql", "?subject <http://www.wikidata.org/prop/direct/P8393> ?qudtid.") #get statement object, 37775 triplets
# wstdict = {**wstdict1, **wstdict2} #merge dicts, 3966 results
wstdict = get_sparql_wikidata_statement_triplets(
    "https://query.wikidata.org/sparql",
    "?subject <http://www.wikidata.org/prop/direct/P279>*/<http://www.wikidata.org/prop/direct/P8393> ?qudtid.",
)  # get statement object
print(len(wstdict))
for st in wstdict:
    for p in wstdict[st]:
        o = wstdict[st][p]
        wdict[st][p] = o  # replace statement with object
wudict1 = get_sparql_triplets(
    "https://query.wikidata.org/sparql",
    "?subject <http://www.wikidata.org/prop/direct/P31> <http://www.wikidata.org/entity/Q47574>.",
)  # instance of unit of measurement: 1340 results
wudict2 = get_sparql_triplets(
    "https://query.wikidata.org/sparql",
    "?subject <http://www.wikidata.org/prop/direct/P5061> ?symbol.",
)  # has unit symbol: 2230 results
wudict3 = get_sparql_triplets(
    "https://query.wikidata.org/sparql",
    "?quantity <http://www.wikidata.org/prop/P8111>/<http://www.wikidata.org/prop/statement/P8111> ?subject.",
)  # is recommended unit of measurement of: 294 results
wudict4 = get_sparql_triplets(
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


# ## Normalize ucum
# 'kg/(m.s2)' -> 'kg.m-1.s-2'

# In[3]:


def normUcumFracToLin(ucum):
    ucum = (
        ucum.replace("[", "(")
        .replace("]", ")")
        .replace("{", "(")
        .replace("}", ")")
    )
    result = ""
    fraction = False
    index = 0
    for c in ucum:  # iterate over all chars
        skip = False
        if c == "/":
            fraction = True
            if index > 0:
                result += "."  # some ucums begin with a '/', no sep '.' needed
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
                    "Warning: negativ exponent in fraction in {}".format(ucum)
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


# ## 1. Validate normalization ucum

# ### function definition: export dictionary as json object

# In[4]:


def dictToJson(dictionary, nameOfJson, optionalOrient=None, optionalPath=None):
    import pandas as pd
    from pathlib import Path

    if optionalOrient is None:
        dfJson = pd.DataFrame.from_dict(dictionary)
    else:
        dfJson = pd.DataFrame.from_dict(dictionary, orient=optionalOrient)
    if optionalPath is None:
        filepathJson = Path(f"./dataExport/{nameOfJson}.json")
    else:
        Path(optionalPath)
    filepathJson.parent.mkdir(parents=True, exist_ok=True)
    dfJson.to_json(filepathJson)


# ### normalize 'kg/(m.s2)' -> 'kg.m-1.s-2'

# In[5]:


ucum_u_dict = {}  # ucum to qudt unit
for u in udict:
    if "http://qudt.org/schema/qudt/ucumCode" in udict[u]:
        if udict[u]["http://qudt.org/schema/qudt/ucumCode"][0] in ucum_u_dict:
            e = udict[u]["http://qudt.org/schema/qudt/ucumCode"][0]
            print(
                "Warning: Conflict for {}: {} vs {}".format(
                    e, u, ucum_u_dict[e]
                )
            )
        ucum_u_dict[udict[u]["http://qudt.org/schema/qudt/ucumCode"][0]] = u
print(len(udict))
print(len(ucum_u_dict))
# uwudict = {} # qudt unit to wiki data unit
ucum_wu_dict = {}  # ucum to wikidata unit
for wu in wudict:
    if (
        "http://www.wikidata.org/prop/direct/P7825" in wudict[wu]
    ):  # and 'http://www.wikidata.org/prop/direct/P5061' in wudict[wu]:
        # print(wudict[wu]['http://www.wikidata.org/prop/direct/P5061'])
        for e in wudict[wu]["http://www.wikidata.org/prop/direct/P7825"]:
            ucum_wu_dict[normUcumFracToLin(e)] = wu
print(len(wudict))
print(len(ucum_wu_dict))


# #### create json objects of dictionaries

# In[6]:


dictToJson(udict, "u_dict_qudt")


# In[7]:


dictToJson(ucum_u_dict, "ucum_u_dict_qudt", "index")


# In[8]:


dictToJson(wudict, "wudict_wikidata")


# In[9]:


dictToJson(ucum_wu_dict, "ucum_wu_dict_wikidata", "index")


# ### function definition: compare string elements of a unit by specific separator
#     a = "erg.cm-2.s-1"
#     b = "erg.s-1.cm-2"
#     c = "erg.s-1.cm-8"
#     separator = "."
#
#     compareUnitElements(a, b, separator, maxsplit=None)
#     --> True
#     compareUnitElements(a, c, separator)
#     --> False

# In[10]:


def compareUnitElements(a, b, separator, maxsplit=None):
    if maxsplit is None:
        maxsplit = -1  # -1 equals all elements in split() defined by seperator
    return sorted(a.split(separator, maxsplit)) == sorted(
        b.split(separator, maxsplit)
    )


import re

regex = r"(?<!\d|-)1(?!\d|/)"  # for positive exponents

dataCleaningDict = {"frac": {}, "exp": {}}

diff_ucum_wucum = {}
diff_ucum_wucumNorm = {}
diff_ucumNorm_wucumNorm = {}
unsorted = {}
counter = 0
for wu in wudict:
    if (
        "http://www.wikidata.org/prop/direct/P2968" in wudict[wu]
        and "http://www.wikidata.org/prop/direct/P7825" in wudict[wu]
    ):  # qudt and ucum defined
        u = wudict[wu]["http://www.wikidata.org/prop/direct-normalized/P2968"][
            0
        ]  # qudt unit
        w_ucum = wudict[wu]["http://www.wikidata.org/prop/direct/P7825"][
            0
        ]  # wikidate ucum

        w_ucum_norm = re.sub(
            regex,
            "",
            normUcumFracToLin(
                wudict[wu]["http://www.wikidata.org/prop/direct/P7825"][0]
            ),
        ).replace(
            "L", "l"
        )  # wikidate ucum normalized

        if (
            u in udict and "http://qudt.org/schema/qudt/ucumCode" in udict[u]
        ):  # ucum defined
            e = udict[u]["http://qudt.org/schema/qudt/ucumCode"][0]

            ucum_norm = re.sub(
                regex,
                "",
                normUcumFracToLin(
                    udict[u]["http://qudt.org/schema/qudt/ucumCode"][0]
                ),
            ).replace(
                "L", "l"
            )  # ucum defined & normalized

            if e != w_ucum:
                diff_ucum_wucum[u] = f"{e} <-> {w_ucum} DIFF FOR {u} <-> {wu}"
            if e != w_ucum_norm:
                diff_ucum_wucumNorm[u] = (
                    f"{e} <-> {w_ucum_norm} DIFF FOR {u} <-> NORM {wu}"
                )
            if ucum_norm != w_ucum_norm:
                if compareUnitElements(ucum_norm, w_ucum_norm, "."):
                    print(f"{ucum_norm} <-> {w_ucum_norm} is just unsorted")
                    counter += 1
                    # diff_ucumNorm_wucumNorm[u] = f"{ucum_norm} <-> {w_ucum_norm} DIFF FOR NORM {u} <-> NORM {wu}"
                    unsorted[u] = (
                        f"{ucum_norm} <-> {w_ucum_norm} DIFF FOR NORM {u} <-> NORM {wu}"
                    )
                else:
                    diff_ucumNorm_wucumNorm[u] = (
                        f"{ucum_norm} <-> {w_ucum_norm} DIFF FOR NORM {u} <-> NORM {wu}"
                    )
                    dataCleaningDict["exp"][ucum_norm] = w_ucum_norm


dictToJson(diff_ucum_wucum, "10diff_ucum_wucum", "index")
print(len(diff_ucum_wucum))
dictToJson(diff_ucum_wucumNorm, "20diff_ucum_wucumNorm", "index")
print(len(diff_ucum_wucumNorm))
dictToJson(diff_ucumNorm_wucumNorm, "30diff_ucumNorm_wucumNorm", "index")
print(len(diff_ucumNorm_wucumNorm))
print("just unsorted counter: ", counter)


# ## 2. Inverse normalize
# 'kg.m-1.s-2' -> 'kg/(m.s2)'

# ### (sub-)function definition: splitString(string, separator, debug=None)
#     splits bracket sensitve string in single element array by using specific separator
#     --> limitations: "()" round brackets
#     --> objective: factorize any equation or unit
#     --> detection of multiple bracket elements and bracket elements with/without factors inside
# fixed issues:
# 1. nested brackets with dots
# 2. bracket input without dot
# 3. more dot's inside pair of brackets

# In[12]:


def splitString(string, separator, debug=None):
    if debug == None:
        debug = False
    linElems = string.split(separator)
    joinedElem = []
    skip = False
    countBracL = 0  # "("
    countBracR = 0  # ")"
    if debug:
        print(linElems, "\n")
    for e in linElems:
        if "(" in e:
            if countBracL == 0:
                joinedElem.append(e)
                countBracL += e.count("(")
                countBracR += e.count(")")
                if debug:
                    print("(-elem =", e)
                    print("countBracL", countBracL)
                    print("countBracR", countBracR)
                if countBracL != countBracR:
                    skip = True
                else:
                    skip = False
                    countBracR = 0
                    countBracL = 0
                    if debug:
                        print("skip:", skip, "\n", "ResetCounter in 1:(\n")
            else:  # not shure if this hole else-block is required anymore
                joinedElem[-1] = separator.join([joinedElem[-1], e])
                countBracL += e.count("(")
                countBracR += e.count(")")
                if debug:
                    print("(-elem in 2=", e)
                    print("countBracL", countBracL)
                    print("countBracR", countBracR)
                    print(
                        "ELSE-BLOCK-REQUIRED"
                    )  # maybe find out in some test cases
                if countBracL != countBracR:
                    skip = True
                else:
                    skip = False
                    countBracR = 0
                    countBracL = 0
                    if debug:
                        print("skip:", skip, "\n", "ResetCounter in 2:(\n")
        elif skip:
            if ")" in e:
                joinedElem[-1] = separator.join([joinedElem[-1], e])
                countBracL += e.count("(")
                countBracR += e.count(")")
                if debug:
                    print(")-elem =", e)
                    print("countBracL", countBracL)
                    print("countBracR", countBracR)
                if countBracL == countBracR:
                    skip = False
                    countBracR = 0
                    countBracL = 0
                    if debug:
                        print("skip:", skip, "\n", "ResetCounter in 3:)\n")
            else:
                countBracL += e.count("(")
                countBracR += e.count(")")
                if debug:
                    print(
                        "iterate update",
                        "\nlast elem:",
                        joinedElem[-1],
                        "\nupd elem:",
                        e,
                    )
                    print("countBracL", countBracL)
                    print("countBracR", countBracR)
                joinedElem[-1] = separator.join([joinedElem[-1], e])
        elif not skip:
            joinedElem.append(e)
            if debug:
                print("no bracket element:", e, "\n")
    if debug:
        print("raw data", string)
        print("joinedElem", joinedElem, "\n")
    return joinedElem


# ### Function definition: inverse normalization
# normUcumLinToFrac(ucum, debug=None)
#
#     debug "True" returns array, no debug returns string
#     brackets "b", negative exponent "-", fraction "/"
#
#     b - /
#     X 0 0 -> #case1: no fraction, right format
#     X 0 1 -> #case2: fraction, right format
#     0 1 0 -> #case3: fraction normalize, positive and negative exponents allowed, without brackets
#     X 1 1 -> #case4: error, double fraction not allowed
#     1 1 0 -> #case5: fraction normalize, positive and negative exponents allowed, with brackets
#
#     400 -> error, num of brackets invalid!
#     404 -> error, undefined!

# In[13]:


def normUcumLinToFrac(ucum, debug=None):
    linElems = []
    numerator = []
    denominator = []
    bracketElems = []
    fracElems = []
    linBracElemLeft = ""
    separator = "."
    brackets = False

    # define debug mode
    if (debug == None) or not debug:
        debug = False
    else:
        debug = True

    # normalize to only round brackets
    ucum = (
        ucum.replace("[", "(")
        .replace("]", ")")
        .replace("{", "(")
        .replace("}", ")")
    )

    # check valid input with/without brackets
    if ucum.count("(") == ucum.count(")"):
        if ("(" or ")") in ucum:
            # print("valid input with brackets:")
            brackets = True
        else:
            # print("valid input without brackets")
            brackets = False
    else:
        if debug:
            return [ucum, "400", "error, num of brackets invalid!"]
        else:
            return "400: error, num of brackets invalid!"
    # case1
    if ("-" not in ucum) and ("/" not in ucum):
        # print("000: no fraction, right format")
        if debug:
            return [ucum, "X00", "case1: no fraction, right format"]
        else:
            return ucum
    # case2
    elif ("-" not in ucum) and ("/" in ucum):
        # print("X01: fraction, right format")
        if ucum[0] == "/":
            # print("first elem: /")
            result = "1" + ucum
        else:
            result = ucum
        if debug:
            return [result, "X01", "case2: fraction, right format"]
        else:
            return result
    # case5, #case3
    elif ("-" in ucum) and ("/" not in ucum):
        # print("010: fraction normalize, positive and negative exponents allowed ")
        # case 5 #valid input with brackets
        if brackets:
            linElems = splitString(ucum, separator)
            for e in linElems:
                if "-" not in e:
                    numerator.append(e)
                else:
                    denominator.append(
                        (e[: e.find("-")] + e[e.find("-") + 1 :])
                    )
            result = "/".join(
                [separator.join(numerator), separator.join(denominator)]
            )
            if debug:
                return [
                    result,
                    "110",
                    "case5: fraction normalize, positive and negative exponents allowed, with brackets",
                ]
            else:
                return result
                # return (''.join(char for char in result if char not in "1")) #filter "1" not ready yet
        # case3 #valid input without brackets
        else:
            linElems = ucum.split(separator)
            for e in linElems:
                if "-" not in e:
                    e = "".join(
                        char for char in e if char not in "1"
                    )  # filters "1", not factor sensitve yet, e.g. 100
                    numerator.append(e)
                else:
                    e = "".join(
                        char for char in e if char not in "1"
                    )  # filters "1", not factor sensitve yet, e.g. 100
                    denominator.append(
                        (e[: e.find("-")] + e[e.find("-") + 1 :])
                    )
            if not numerator:
                numerator.append("1")
            if len(denominator) > 1:
                result = "/".join(
                    [
                        separator.join(numerator),
                        "(" + separator.join(denominator) + ")",
                    ]
                )
            else:
                result = "/".join(
                    [separator.join(numerator), separator.join(denominator)]
                )
            if debug:
                return [
                    result,
                    "010",
                    "case3: fraction normalize, positive and negative exponents allowed, without brackets",
                ]
            else:
                return result
            # return (''.join(char for char in result if char not in "1")) #filter "1" not ready yet
    # case4
    elif ("-" in ucum) and ("/" in ucum):
        if debug:
            return [ucum, "X11", "case4: error, double fraction not allowed"]
        else:
            return "case4: error, double fraction not allowed"
    # undefined
    else:
        if debug:
            return [ucum, "404", "error, undefined!"]
        else:
            return "error, undefined!"


# ## 3. Validate inverse normalize
#

# ### Inverse Normalize: UCUM DATA

# #### REGEX EXAMPLE: Filter single ones (positive exponents) + replace "L"

# In[14]:


import re

regex = r"(?<!\d)1(?!\d|/)"  # for positive exponents
# regex = r"(?<!\d|-)1(?!\d|/)" #for negative exponent case sensitivity of "-" detect

test_str = "[cft_i].s-1.11.23.231.123L45.5.12.2.4L.5.[1].s5.m2.l1.m-1.1/m"

matches = re.finditer(regex, test_str, re.MULTILINE)


for matchNum, match in enumerate(matches, start=1):

    print(
        "Match {matchNum} was found at {start}-{end}: {match}".format(
            matchNum=matchNum,
            start=match.start(),
            end=match.end(),
            match=match.group(),
        )
    )

    for groupNum in range(0, len(match.groups())):
        groupNum = groupNum + 1

        print(
            "Group {groupNum} found at {start}-{end}: {group}".format(
                groupNum=groupNum,
                start=match.start(groupNum),
                end=match.end(groupNum),
                group=match.group(groupNum),
            )
        )


print(
    "\nReplace single 1-digit in string",
    "\npre: ",
    test_str,
    "\npast:",
    re.sub(regex, "REPLACEMENT", test_str).replace("L", "l"),
)


# #### Valitation with regex

# In[15]:


import re

regex = r"(?<!\d)1(?!\d|/)"  # for positive exponents

diff_ucum_wucum_inv = {}
diff_ucum_wucumNorm_inv = {}
diff_ucumNorm_wucumNorm_inv = {}
diffCasefold_ucumNorm_wucumNorm = {}
unsorted_inv = {}
counter = 0
for wu in wudict:
    if (
        "http://www.wikidata.org/prop/direct/P2968" in wudict[wu]
        and "http://www.wikidata.org/prop/direct/P7825" in wudict[wu]
    ):  # qudt and ucum defined
        u = wudict[wu]["http://www.wikidata.org/prop/direct-normalized/P2968"][
            0
        ]  # qudt unit
        w_ucum = wudict[wu]["http://www.wikidata.org/prop/direct/P7825"][
            0
        ]  # wikidate ucum

        w_ucum_norm = re.sub(
            regex,
            "",
            normUcumLinToFrac(
                wudict[wu]["http://www.wikidata.org/prop/direct/P7825"][0]
            ),
        ).replace(
            "L", "l"
        )  # wikidate ucum normalized
        if (
            u in udict and "http://qudt.org/schema/qudt/ucumCode" in udict[u]
        ):  # ucum defined
            e = udict[u]["http://qudt.org/schema/qudt/ucumCode"][0]
            ucum_norm = re.sub(regex, "", normUcumLinToFrac(e)).replace(
                "L", "l"
            )  # ucum defined & normalized
            if e != w_ucum:
                diff_ucum_wucum_inv[u] = (
                    f"{e} <-> {w_ucum} DIFF FOR {u} <-> {wu}"
                )
            if e != w_ucum_norm:
                diff_ucum_wucumNorm_inv[u] = (
                    f"{e} <-> {w_ucum_norm} DIFF FOR {u} <-> NORM {wu}"
                )
            if ucum_norm != w_ucum_norm:
                if compareUnitElements(
                    normUcumFracToLin(ucum_norm),
                    normUcumFracToLin(w_ucum_norm),
                    ".",
                ):
                    # if compareUnitElements(ucum_norm, w_ucum_norm, "."):
                    print(f"{ucum_norm} <-> {w_ucum_norm} is just unsorted")
                    counter += 1
                    # diff_ucumNorm_wucumNorm_inv[u] = f"{ucum_norm} <-> {w_ucum_norm} DIFF FOR NORM {u} <-> NORM {wu}"
                    unsorted_inv[u] = (
                        f"{ucum_norm} <-> {w_ucum_norm} DIFF FOR NORM {u} <-> NORM {wu}"
                    )
                else:
                    diff_ucumNorm_wucumNorm_inv[u] = (
                        f"{ucum_norm} <-> {w_ucum_norm} DIFF FOR NORM {u} <-> NORM {wu}"
                    )
                    dataCleaningDict["frac"][ucum_norm] = w_ucum_norm


dictToJson(diff_ucum_wucum_inv, "10diff_ucum_wucum_inv", "index")
print(len(diff_ucum_wucum_inv))
dictToJson(diff_ucum_wucumNorm_inv, "20diff_ucum_wucumNorm_inv", "index")
print(len(diff_ucum_wucumNorm_inv))
dictToJson(
    diff_ucumNorm_wucumNorm_inv, "30diff_ucumNorm_wucumNorm_inv", "index"
)
print(len(diff_ucumNorm_wucumNorm_inv))
print("just unsorted counter: ", counter)


# In[16]:


# check differences of FracToLin and LinToFrac normalizations
diff_normFunctions = {}
both_counter = 0

print("diff_ucumNorm_wucumNorm_inv LENGTH", len(diff_ucumNorm_wucumNorm_inv))
print("diff_ucumNorm_wucumNorm LENGHT: ", len(diff_ucumNorm_wucumNorm))

print("\nNOT IN NORM_INV")
for k, v in diff_ucumNorm_wucumNorm.items():
    if k in diff_ucumNorm_wucumNorm_inv.keys():
        # print(k, v)
        both_counter += 1
    else:
        diff_normFunctions[k] = v
        print(k, v)

print("both_counter = ", both_counter)
print("not in both coutner= ", len(diff_normFunctions))

diff_normFunctions = {}
both_counter = 0
print("\nNOT IN NORM")
for k, v in diff_ucumNorm_wucumNorm_inv.items():
    if k in diff_ucumNorm_wucumNorm.keys():
        # print(k, v)
        both_counter += 1
    else:
        diff_normFunctions[k] = v
        print(k, v)

print("both_counter = ", both_counter)
print("not in both coutner= ", len(diff_normFunctions))


# In[17]:


print(len(unsorted_inv))
print(len(unsorted))

print("just unsorted_inv")
for k, v in unsorted_inv.items():
    print(k, v)

print("just unsorted")
for k, v in unsorted.items():
    print(k, v)


# In[18]:


# show cleaning dict, this has to be sorted manually afterwards
import pprint

pprint.pprint(dataCleaningDict)


# In[19]:


# copy & paste cleaining dict and bring key-value-pairs in right order
# key is NOT allowed ucum, value is allowed ucum

dataCleaningDict = {
    "exp": {
        "(Btu_th)": "(Btu)",
        "(cft_i).s-1": "(ft_i)3.s-1",
        "(cft_i)/s": "(ft_i)3.s-1",
        "(ft_i)/h": "(ft_i).h-1",
        "(cft_i)": "(ft_i)3",
        "(cft_i)/min": "(ft_i)3.min-1",
        "(ft_i)3/min": "(ft_i)3.min-1",
        "(cin_i)": "(in_i)3",
        "(lb_av).(cft_i)-1": "(lb_av)/(ft_i)3",
        "(lb_av).(cin_i)-1": "(lb_av).(in_i)-3",
        "(lb_av)/(cin_i)": "(lb_av).(in_i)-3",
        "(lb_av).(cyd_i)-1": "(lb_av)/(yd_i)3",
        "(lbf_av).(sin_i)-1": "(psi)",
        "(mi_i)/min": "(mi_i).min-1",
        "(smi_us)": "(mi_us)2",
        "(sft_i).h-1": "(ft_i)2.h-1",
        "(ft_i)2/h": "(ft_i)2.h-1",
        "(sft_i).s-1": "(ft_i)2.s-1",
        "(ft_i)2/s": "(ft_i)2.s-1",
        "(sin_i).s-1": "(in_i)2.s-1",
        "(in_i)2/s": "(in_i)2.s-1",
        "(syd_i)": "(yd_i)2",
        "A.m-2.K-1": "A.m-2.K-2",
        "Bd": "bit.s-1",
        "C.m-3": "C.cm-3",
        "GP": "GPa",
        "N.m.kg-2": "N.m2.kg-2",
        "N.m.s-1": "N.m.s",
        "P.s.m-1": "Pa.s.m-1",
        "S.cm-2": "S.cm-1",
        "TW.h-1": "TW.h",
        "eV.s-1": "eV.s",
        "kbit.s-2": "kbit.s-1",
        "kcal_th": "kcal",
        "kg.(s.m2)-1": "kg.m-2.s-1",
        "kg.mol-1": "kg.kmol-1",
        "lm.s-1": "lm.s",
        'm"': "m''",
        "m3.(kg.s2)-1": "m3.kg-1.s-2",
        "minbreath-1": "(breaths).min-1",
        "(breaths)/min": "(breaths).min-1",
        "rad.m-2.mol-1": "rad.m2.mol-1",
    },
    "frac": {
        "(Btu_th)": "(Btu)",
        "(cft_i)": "(ft_i)3",
        "(cft_i)/min": "(ft_i)3/min",
        "(cin_i)": "(in_i)3",
        "(lb_av)/(cft_i)": "(lb_av)/(ft_i)3",
        "(lb_av)/(cyd_i)": "(lb_av)/(yd_i)3",
        "(lbf_av)/(sin_i)": "(psi)",
        "(smi_us)": "(mi_us)2",
        "(sft_i)/h": "(ft_i)2/h",
        "(sft_i)/s": "(ft_i)2/s",
        "(sin_i)/s": "(in_i)2/s",
        "(syd_i)": "(yd_i)2",
        "1/min(breath)": "(breaths)/min",
        "A/(m2.K)": "A/(m2.K2)",
        "Bd": "bit/s",
        "C/m3": "C/cm3",
        "GP": "GPa",
        "N.m/kg2": "N.m2/kg2",
        "N.m/s": "N.m.s",
        "P.s/m": "Pa.s/m",
        "S/cm2": "S/cm",
        "TW/h": "TW.h",
        "eV/s": "eV.s",
        "kbit/s2": "kbit/s",
        "kcal_th": "kcal",
        "kg/mol": "kg/kmol",
        "lm/s": "lm.s",
        'm"': "m''",
        "rad/(m2.mol)": "rad.m2/mol",
    },
}


# ## 4. Ucum-Mapping-Dictionary
#

# ### Define regex wrapper
#
# - eliminate "1"-factors
# - change "L" uppercase to "l" lowercase

# #### normUcumFracToLin() + regex + "L" to lowercase

# In[20]:


def normRegUcumFTL(ucum):
    import re

    regex = r"(?<!\d|-)1(?!\d|/)"  # for positive exponents
    return re.sub(regex, "", normUcumFracToLin(ucum)).replace(
        "L", "l"
    )  # ucum defined & normalized


# ##### test wrapper FTL

# In[21]:


FTL = "1/m"

print(normUcumFracToLin(FTL))
print(normRegUcumFTL(FTL))


# #### normUcumLinToFrac() + regex + "L" to lowercase

# In[22]:


def normRegUcumLTF(ucum):
    if "1" or "L" in ucum:
        import re

        # regex = r"(?<!\d)1(?!\d|/)"
        regex = r"(?<!\d)1(?!\d)"
        return re.sub(regex, "", normUcumLinToFrac(ucum)).replace(
            "L", "l"
        )  # ucum defined & normalized
    else:
        return ucum


# In[23]:


def normRegUcumLTF(ucum):
    if "1" or "L" in ucum:
        import re

        regex = r"(?<!\d)1(?!\d)"  # filter all ones without digit neigbours
        ucum = re.sub(regex, "", normUcumLinToFrac(ucum)).replace("L", "l")
        if ucum[0] == "/":
            ucum = "1" + ucum
        return ucum  # ucum defined & normalized
    else:
        return ucum


# ##### test wrapper LTF

# In[24]:


testarray = [
    "(kg.m)1.s-1",
    "(kg.m)-1.s-1",
    "(kg.m)-2.s-1",
    "kg-1",
    "[cft_i].s-1.11.23.231.123L45.5.12.2.4L.5.[1].s5.m2.l1.m-1.1/m.1.1/sdf",
    "1/L",
    "L-1",
]

for LTF in testarray:
    print("normLTF: ", normUcumLinToFrac(LTF))
    print("LTF+REG: ", normRegUcumLTF(LTF), "\n")


# ### Create mapping dict

# In[ ]:


# ucum mapping dictionary
ucumMappingDict = {}


# In[ ]:
