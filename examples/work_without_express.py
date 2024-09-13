from pathlib import Path

from osw.auth import CredentialManager
from osw.core import OSW
from osw.wtsite import WtSite

cred_fp = Path("accounts.pwd.yaml")
# domain = "arkeve.test.digital.isc.fraunhofer.de"
# domain = "wiki-dev.open-semantic-lab.org"
domain = "test.kav.isc.fraunhofer.de"
# cred_man = CredentialManager(cred_filepath=cred_fp)
cred_man = CredentialManager()
osw_obj = OSW(site=WtSite(WtSite.WtSiteConfig(iri=domain, cred_mngr=cred_man)))
# cred_man.save_credentials_to_file()
