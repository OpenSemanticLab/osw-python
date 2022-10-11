# pip available modules
import sys
import qgrid
import pprint
import copy
import getpass
import fs.smbfs
from pathlib import Path
sys.path.append('//src')
import wiki_tools as wt

# network storage fiel system authentication
user = input("Username")
password = getpass.getpass("Password")
smb_fs = fs.smbfs.SMBFS(
    ('wuestore','10.88.50.107'), username=user, passwd=password, domain='ISC', timeout=15)
del user, password




# wiki authentication of the source system
site1 = wt.create_site_object("wiki-dev")

# wiki authentication of the target system
site2 = wt.create_site_object("testwiki")#wt.create_site_object("testwiki")