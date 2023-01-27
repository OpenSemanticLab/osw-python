# from quantities
import getpass

from SPARQLWrapper import BASIC, JSON, POST, SPARQLWrapper


class SmwSparqlClient:
    def __init__(self, endpoint, domain, auth="none", user="", password=""):

        self.create_sparql_client(endpoint, auth, user, password)

        self.prefix_dict = {
            "dc": "http://purl.org/dc/elements/1.1/",
            "property": "https://{domain}/id/Property-3A",
            "file": "https://{domain}/id/File-3A",
            "category": "https://{domain}/id/Category-3A",
            "material": "https://{domain}/id/Material-3A",
            "wiki": "https://{domain}/id/",
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "owl": "http://www.w3.org/2002/07/owl#",
            "swivt": "http://semantic-mediawiki.org/swivt/1.0#",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
        }
        self.wiki_prefixes = []
        self.prefixes = ""
        for prefix in self.prefix_dict:
            if "{domain}" in prefix:
                self.wiki_prefixes.append[prefix]
            self.prefix_dict[prefix] = self.prefix_dict[prefix].replace(
                "{domain}", domain
            )
            self.prefixes += f"PREFIX {prefix}: <{self.prefix_dict[prefix]}>\n".replace(
                "{domain}", domain
            )

        # from https://github.com/SemanticMediaWiki/SemanticMediaWiki/blob/e04b78ddbc0a1b2181b12f31a51d7f91e723336b/src/Exporter/Escaper.php#L61
        self.smw_encoding_lists = {
            "in": [
                "*",
                ",",
                ";",
                "<",
                ">",
                "(",
                ")",
                "[",
                "]",
                "{",
                "}",
                "\\",
                "$",
                "^",
                ":",
                '"',
                "#",
                "&",
                "'",
                "+",
                "!",
                "%",
            ],
            "out": [
                "-2A",
                "-2C",
                "-3B",
                "-3C",
                "-3E",
                "-28",
                "-29",
                "-5B",
                "-5D",
                "-7B",
                "-7D",
                "-5C",
                "-24",
                "-5E",
                "-3A",
                "-22",
                "-23",
                "-26",
                "-27",
                "-2B",
                "-21",
                "-",
            ],
        }
        self.encoding_dict = dict(
            zip(self.smw_encoding_lists["in"], self.smw_encoding_lists["out"])
        )
        self.encoding_dict = {}
        self.encoding_dict_inv = dict(
            (self.encoding_dict[k], k) for k in self.encoding_dict
        )

    def create_sparql_client(self, endpoint, auth="none", user="", password=""):
        self.sparql = SPARQLWrapper(endpoint)
        if auth == "basic":
            self.sparql.setHTTPAuth(BASIC)
            if user == "":
                user = input("Enter username")
            if password == "":
                password = getpass.getpass("Enter password")
            self.sparql.setCredentials(user, password)
        self.sparql.setMethod(POST)

    def sparqlQuery(self, query):
        # print(query)
        self.sparql.setQuery(query)
        self.sparql.setReturnFormat(JSON)
        # print(self.sparql.query())
        return self.sparql.query().convert()

    def get_sparql_triplets(
        self,
        where_statement,
        select_statement="",
        inner_where_statement="?subject ?predicate ?object",
        tsubject="",
        tpredicate="",
        tobject="",
        limit=999999999,
        prefixes="",
        debug=False,
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
        if prefixes == "":
            prefixes = self.prefixes
        query = (
            """
            {{{prefixes}}}
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
            .replace("{{{prefixes}}}", prefixes)
        )
        for key in self.encoding_dict.keys():
            query = query.replace(key, self.encoding_dict[key])
        if debug:
            print(query)
        # select distinct ?p ?o where {<http://dbpedia.org/resource/Amount_of_substance> ?p ?o} LIMIT 100
        triples = self.sparqlQuery(query)
        # print(triples)
        tdict = {}
        if debug:
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
            for prefix in self.prefix_dict:
                s = s.replace(self.prefix_dict[prefix], prefix + ":")
                p = p.replace(self.prefix_dict[prefix], prefix + ":")
                o = o.replace(self.prefix_dict[prefix], prefix + ":")
            for key in self.encoding_dict_inv.keys():
                s = s.replace(key, self.encoding_dict_inv[key])
                p = p.replace(key, self.encoding_dict_inv[key])
                o = o.replace(key, self.encoding_dict_inv[key])
            self.dict_append_tripl(tdict, s, p, o)
        # print(tdict)
        return tdict

    def spo_result_to_dict(self, triples, tsubject="", tpredicate="", tobject=""):
        tdict = {}
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
            for prefix in self.prefix_dict:
                s = s.replace(self.prefix_dict[prefix], prefix + ":")
                p = p.replace(self.prefix_dict[prefix], prefix + ":")
                o = o.replace(self.prefix_dict[prefix], prefix + ":")
            self.dict_append_tripl(tdict, s, p, o)
        # print(tdict)
        return tdict

    def dict_append_tripl(self, d, s, p, o):
        if s not in d:
            d[s] = {}
        if p not in d[s]:
            d[s][p] = []
        d[s][p].append(o)
