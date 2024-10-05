import os
from io import StringIO

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.express import OswExpress
from osw.utils.wiki import get_full_title

# Install: pip install osw[S3]

# Credential manager (can use a file or hardcode the credentials, otherwise the user
#  will be prompted to enter them)
cm = CredentialManager(
    cred_filepath=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
    )
)
# Change the domain to your osw instance
osw_obj = OswExpress(domain="wiki-dev.open-semantic-lab.org", cred_mngr=cm)

# Load the required schemas / data classes
if not hasattr(model, "S3File"):
    DEPENDENCIES = {
        "S3File": "Category:OSWc43f749badcb4490a785505de1fc7d20",
        "LocalFile": "Category:OSW3e3f5dd4f71842fbb8f270e511af8031",
        "WikiFile": "Category:OSW11a53cdfbdc24524bf8ac435cbf65d9d",
    }
    osw_obj.install_dependencies(DEPENDENCIES, mode="replace")

# Import the controller modules
# Note: since they depend on the data classes, they must be imported after the schemas
#  are loaded
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
    # Create a local file
    # with open("dummy.txt", "w") as f:
    #    f.write("Hello World!")
    lf = LocalFileController(path="dummy.txt")  # here an uuid already exists
    lf.put(StringIO("Hello World!"))

    # Create a remote file (here: a wiki file)
    wf = WikiFileController(osw=osw_obj)
    # Or cast to wiki wile to keep all common attributes
    wf = lf.cast(WikiFileController, osw=osw_obj)
    # Which is equivalent to
    wf = WikiFileController.from_other(lf, osw=osw_obj)

    # Upload the local file to the remote file
    wf.put_from(lf)
    # Write new content on the fly
    wf.put(StringIO("Some new content"))

    # Get an existing file
    file = osw_obj.load_entity(f"{wf.namespace}:{wf.title}")  # the file
    wf2 = file.cast(WikiFileController, osw=osw_obj)  # the file controller
    lf2 = LocalFileController.from_other(wf2, path="dummy2.txt")
    lf2.put_from(wf2)
    get_full_title(wf2)

    # Delete the files
    lf.delete()
    wf.delete()  # note: wf2 actually points to the same file as wf
    lf2.delete()


def s3_file():
    # Make sure your credential file contains a access_key_id=username,
    #  and secret_access_key=password for the s3 domain
    file = osw_obj.load_entity("Item:OSW5f53ed0b5c354fc3b1a122b9066744f3")  # the file
    s3f = file.cast(S3FileController, cm=cm)  # the file controller

    # Download
    lf = LocalFileController.from_other(s3f, path="s3_test.txt")
    lf.put_from(s3f)

    # Upload
    s3f.put_from(lf)

    s3f = model.S3File(
        url="https://s3.example10.open-semantic-lab.org/test-bucket/test-example2.txt",
        label=[model.Label(text="NewFile")],
    ).cast(S3FileController, cm=cm)
    s3f.put(StringIO("Hello World!"))

    s3f.delete()
