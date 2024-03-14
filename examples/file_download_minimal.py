from osw.express import osw_download_file

# Download a file from an OSW instance and save it to a local file
local_file = osw_download_file(
    "https://wiki-dev.open-semantic-lab.org/wiki/"
    "File:OSWaa635a571dfb4aa682e43b98937f5dd3.pdf"
    # , use_cached=True
    # , overwrite=True
)
local_file_path = local_file.path
