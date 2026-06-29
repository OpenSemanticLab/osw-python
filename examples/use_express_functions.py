import os
from pathlib import Path

import dotenv

from osw.express import OswExpress, osw_download_file, osw_upload_file  # noqa: E402

# Best practise load environment variables from .env file
dotenv.load_dotenv()  # will look for a .env file in CWD and above

# (Alternative) Setting the domain of the wiki to connect to
os.environ["OSW_WIKI_DOMAIN"] = "wiki-dev.open-semantic-lab.org"
# (Optional) Set the default credentials filepath to desired location. Otherwise,
#  it will use the default location (current working directory)
os.environ["OSW_CRED_FILEPATH"] = str(
    Path(__file__).parent / "osw_files" / "accounts.pwd.yaml"
)

# The domain to connect to
domain = "wiki-dev.open-semantic-lab.org"
# domain = "demo.open-semantic-lab.org"
# Create an OswExpress object
osw_obj = OswExpress(domain=domain)

# (Alternative, here equivalent to) loading domain from the environment variable
osw_obj = OswExpress()

# Create a file
fp = Path("example.txt")
with open(fp, "w") as file:
    file.write("Hello, World!")
# Upload a file to an OSW instance
wiki_file = osw_upload_file(fp, domain=domain)
# Delete WikiFile from OSW instance
wiki_file.delete()
# Delete a file
fp.unlink()

# Download a file from an OSW instance and save it to a local file
local_file = osw_download_file(
    "https://wiki-dev.open-semantic-lab.org/wiki/"
    "File:OSWaa635a571dfb4aa682e43b98937f5dd3.pdf",
    overwrite=True,  # Required if file already exists
)
local_file_path = local_file.path

# Open a file with context manager directly from an OSW instance
with osw_download_file(
    "File:OSWac9224e1a280449dba71d945b1581d57.txt",
    domain=domain,
    overwrite=True,  # Required if file already exists
) as file:
    content = file.read()
