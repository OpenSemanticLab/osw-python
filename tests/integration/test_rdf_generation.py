import json

from jsondiff import diff

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.core import OSW
from osw.utils.wiki import get_full_title
from osw.wtsite import WtSite


# run with: tox -e test -- --wiki_domain domain --wiki_username user --wiki_password pass
def test_local_rdf_graph_with_remote_context(wiki_domain, wiki_username, wiki_password):
    cm = CredentialManager()
    cm.add_credential(
        CredentialManager.UserPwdCredential(
            iri=wiki_domain, username=wiki_username, password=wiki_password
        )
    )
    wtsite = WtSite(WtSite.WtSiteConfig(iri=wiki_domain, cred_mngr=cm))
    osw_obj = OSW(site=wtsite)

    i1 = model.Item(name="MyItem", label=[model.Label(text="My Item")])
    i2 = model.Item(
        name="MyItem2",
        label=[model.Label(text="My Item 2")],
        based_on=[get_full_title(i1)],
    )

    res = osw_obj.export_jsonld(
        params=OSW.ExportJsonLdParams(
            entities=[i1, i2],
            mode=OSW.JsonLdMode.expand,
            build_rdf_graph=True,
            additional_context="https://json-ld.org/contexts/remote-context.jsonld",
        )
    )

    qres = res.graph.query(
        """
        SELECT ?pname ?oname
        WHERE {
        ?s <https://www.w3.org/TR/skos-reference/isBasedOn> ?o .
        ?s Property:HasName ?pname .
        ?o Property:HasName ?oname
        }
        """
    )

    # export Sparql query results as json
    actual = json.loads(qres.serialize(format="json"))
    expected = {
        "results": {
            "bindings": [
                {
                    "oname": {"type": "literal", "value": "MyItem"},
                    "pname": {"type": "literal", "value": "MyItem2"},
                }
            ]
        },
        "head": {"vars": ["pname", "oname"]},
    }
    diff_dict = diff(expected, actual, syntax="explicit")
    print("expected - actual diff: ", diff_dict)
    assert actual == expected
