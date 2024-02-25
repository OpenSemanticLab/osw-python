from osw.express import OswExpress, credentials_fp_default, osw_download_file, osw_open

# (Optional) Set the default credentials filepath to desired location. Otherwise,
# it will use the default location (current working directory)
credentials_fp_default.set_default(r"C:\Users\gold\ownCloud\Personal\accounts.pwd.yaml")

# Create an OswExpress object
# domain = "wiki-dev.open-semantic-lab.org"
domain = "arkeve.test.digital.isc.fraunhofer.de"
osw = OswExpress(domain=domain)

# Download a file from an OSW instance and save it to a local file
local_file = osw_download_file(
    "https://wiki-dev.open-semantic-lab.org/wiki/"
    "File:OSWaa635a571dfb4aa682e43b98937f5dd3.pdf",
    overwrite=True,
)
local_file_path = local_file.path
# Open the file with context manager directly from an OSW instance
with osw_open(
    "https://wiki-dev.open-semantic-lab.org/wiki/"
    "File:OSWac9224e1a280449dba71d945b1581d57.txt"
) as file:
    content = file.read()
# Doesn't work yet:
# with osw_download_file(
#         "File:OSWac9224e1a280449dba71d945b1581d57.txt", domain=domain,
#         overwrite=True
# ) as file:
#     content2 = file.read()
