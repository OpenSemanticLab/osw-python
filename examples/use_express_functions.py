from pathlib import Path

from osw.express import (
    OswExpress,
    cred_filepath_default,
    osw_download_file,
    osw_upload_file,
)

# (Optional) Set the default credentials filepath to desired location. Otherwise,
#  it will use the default location (current working directory)
# cred_filepath_default.set_default(r"C:\Users\gold\ownCloud\Personal\accounts.pwd.yaml")

# Check setting
print(f"Credentials loaded from '{str(cred_filepath_default)}")

# Create an OswExpress object
domain = "wiki-dev.open-semantic-lab.org"
# domain = "arkeve.test.digital.isc.fraunhofer.de"
osw_obj = OswExpress(domain=domain)

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
local_file.close()  # required to release the file lock

# Open a file with context manager directly from an OSW instance
with osw_download_file(
    "File:OSWac9224e1a280449dba71d945b1581d57.txt",
    domain=domain,
    overwrite=True,  # Required if file already exists
) as file:
    content = file.read()
