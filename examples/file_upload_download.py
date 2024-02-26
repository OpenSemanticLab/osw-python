import os
from io import StringIO

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.core import OSW
from osw.utils.wiki import get_full_title
from osw.wtsite import WtSite

# install: pip install osw[S3]

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
osw_obj = OSW(
    site=WtSite(WtSite.WtSiteConfig(iri="wiki-dev.open-semantic-lab.org", cred_mngr=cm))
)

# load the required schemas / data classes
if not hasattr(model, "S3File"):
    osw_obj.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title=[
                "Category:OSW11a53cdfbdc24524bf8ac435cbf65d9d",  # WikiFile
                "Category:OSW3e3f5dd4f71842fbb8f270e511af8031",  # LocalFile
                "Category:OSWc43f749badcb4490a785505de1fc7d20",  # S3File
            ],
            mode="replace",
        )
    )

# import the controller modules
# note: since they depend on the data classes, they must be imported after the schemas are loaded
from osw.controller.file.local import (  # noqa (ignore flake8 warning)
    LocalFileController,
)
from osw.controller.file.s3 import S3FileController  # noqa (ignore flake8 warning)
from osw.controller.file.wiki import WikiFileController  # noqa (ignore flake8 warning)


def video_file():
    file = osw_obj.load_entity(
        "File:OSW7b2398a60f004006b9a6ef89210858f3.mp4"
    )  # the file
    wf2 = file.cast(WikiFileController, osw=osw_obj)  # the file controller
    # wf2.suffix = "mp4"
    lf2 = LocalFileController.from_other(wf2, path="dummy2.mp4")
    lf2.put_from(wf2)


def wiki_file():
    # create a local file
    # with open("dummy.txt", "w") as f:
    #    f.write("Hello World!")
    lf = LocalFileController(path="dummy.txt")  # here an uuid already exists
    lf.put(StringIO("Hello World!"))

    # create a remote file (here: a wiki file)
    wf = WikiFileController(osw=osw_obj)
    # or cast to wiki wile to keep all common attributes
    wf = lf.cast(WikiFileController, osw=osw_obj)
    # which is equivalent to
    wf = WikiFileController.from_other(lf, osw=osw_obj)

    # upload the local file to the remote file
    wf.put_from(lf)
    # write new content on the fly
    wf.put(StringIO("Some new content"))

    # get an existing file
    file = osw_obj.load_entity(f"{wf.namespace}:{wf.title}")  # the file
    wf2 = file.cast(WikiFileController, osw=osw_obj)  # the file controller
    lf2 = LocalFileController.from_other(wf2, path="dummy2.txt")
    lf2.put_from(wf2)
    get_full_title(wf2)

    # delete the files
    lf.delete()
    wf.delete()  # note: wf2 actually points to the same file as wf
    lf2.delete()


def s3_file():
    # make sure your credential file contains a access_key_id=username,
    # and secret_access_key=password for the s3 domain
    file = osw_obj.load_entity("Item:OSW5f53ed0b5c354fc3b1a122b9066744f3")  # the file
    s3f = file.cast(S3FileController, cm=cm)  # the file controller

    # download
    lf = LocalFileController.from_other(s3f, path="s3_test.txt")
    lf.put_from(s3f)

    # upload
    s3f.put_from(lf)

    s3f = model.S3File(
        url="https://s3.example10.open-semantic-lab.org/test-bucket/test-example2.txt",
        label=[model.Label(text="NewFile")],
    ).cast(S3FileController, cm=cm)
    s3f.put(StringIO("Hello World!"))

    s3f.delete()
