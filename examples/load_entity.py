import os

from osw.osl import OSL
from osw.wtsite import WtSite

# create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)
# pwd_file_path = "./accounts.pwd.yaml"
wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)
osl = OSL(site=wtsite)

title = "Item:OSL7d7193567ea14e4e89b74de88983b718"
# title = "Item:OSLe02213b6c4664d04834355dc8eb08b99"
entity = osl.load_entity(title)
print(entity.__class__)
print(entity)
