from osw.express import osw_download_file

# Download a file from an OSW instance and save it to a local file
local_file = osw_download_file(
    "https://wiki-dev.open-semantic-lab.org/wiki/"
    "File:OSW3bbf46a9a271409bb6d75728df318a95.png"
    # , use_cached=True
    # , overwrite=True
)
local_file_path = local_file.path
