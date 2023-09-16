import os
from io import StringIO

from osw.auth import CredentialManager
from osw.core import OSW
from osw.wtsite import WtSite

# credential manager
# can use a file or hardcode the credentials, otherwise the user will be prompted to enter them
cm = CredentialManager(
    cred_filepath=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
    )
    # CredentialManager.UserPwdCredential(
    #     iri=wiki_domain, username=wiki_username, password=wiki_password
    # )
)
# change the domain to your osw instance
osw = OSW(
    wtsite=WtSite(
        WtSite.WtSiteConfig(iri="wiki-dev.open-semantic-lab.org", cred_mngr=cm)
    )
)

# load the required schemas / data classes
osw.fetch_schema(
    OSW.FetchSchemaParam(
        schema_title=[
            "Category:OSW11a53cdfbdc24524bf8ac435cbf65d9d",  # WikiFile
            "Category:OSW3e3f5dd4f71842fbb8f270e511af8031",  # LocalFile
        ],
        mode="replace",
    )
)

# import the controller modules
# note: since they depend on the data classes, they must be imported after the schemas are loaded
from osw.controller.file.local import (  # noqa (ignore flake8 warning)
    LocalFileController,
)
from osw.controller.file.wiki import WikiFileController  # noqa (ignore flake8 warning)

# create a local file
# with open("dummy.txt", "w") as f:
#    f.write("Hello World!")
lf = LocalFileController(path="dummy.txt")
lf.put(StringIO("Hello World!"))

# create a remote file (here: a wiki file)
wf = WikiFileController(osw=osw)
# or cast to wiki wile to keep all common attributes
wf = lf.cast(WikiFileController, osw=osw)
# which is equivalent to
wf = WikiFileController.from_other(lf, osw=osw)

# upload the local file to the remote file
wf.put_from(lf)
# write new content on the fly
wf.put(StringIO("Some new content"))

# get an existing file
file = osw.load_entity(f"{wf.namespace}:{wf.title}")  # the file
wf2 = file.cast(WikiFileController, osw=osw)  # the file controller
lf2 = LocalFileController.from_other(wf2, path="dummy2.txt")
lf2.put_from(wf2)

# delete the files
lf.delete()
wf.delete()  # note: wf2 actually points to the same file as wf
lf2.delete()
