from osw.sparql_client_smw import SmwSparqlClient

domain = "onterface.open-semantic-lab.org"


def test_osl_id_to_uuid():
    sc = SmwSparqlClient(
        f"https://graph.{domain}/blazegraph/namespace/kb/sparql", domain
    )
    result = sc.get_sparql_triplets(
        where_statement=f"?subject swivt:page <https://{domain}/wiki/Main_Page>"
    )
    result_value = result["wiki:Main_Page"]["rdfs:isDefinedBy"][0]
    expected_value = f"https://{domain}/wiki/Special:ExportRDF/Main_Page"
    assert result_value == expected_value
