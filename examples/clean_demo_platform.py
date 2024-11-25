from pathlib import Path

import osw.params as prm
from osw.express import OswExpress

osw_obj = OswExpress(
    domain="demo.open-semantic-lab.org", cred_filepath=Path("accounts.pwd.yaml")
)
orgs = osw_obj.site.semantic_search(
    prm.SearchParam(
        query="[[HasType::Category:OSW1969007d5acf40539642877659a02c23]]", debug=False
    )
)
persons = osw_obj.site.semantic_search(
    prm.SearchParam(
        query="[[HasType::Category:OSW44deaa5b806d41a2a88594f562b110e9]]", debug=False
    )
)
osw_obj.site.delete_page(orgs + persons)
