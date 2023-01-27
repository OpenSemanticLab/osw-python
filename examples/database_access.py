import os

# import osw.controller.entity as controller
import osw.model.entity as model
from osw.core import OSW
from osw.wtsite import WtSite

# create/update the password file under examples/accounts.pwd.yaml
pwd_file_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "accounts.pwd.yaml"
)
# pwd_file_path = "./accounts.pwd.yaml"
wtsite = WtSite.from_domain("wiki-dev.open-semantic-lab.org", pwd_file_path)
osw = OSW(site=wtsite)

wtsite.enable_cache()  # skip downloads on second request

# osw.fetch_schema() #this will load the current entity schema from the OSW instance. You may have to re-run the script to get the updated schema extension. Requires 'pip install datamodel-code-generator'
if False:
    osw.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title="Category:OSW02590972aeba46d7864ed492c0c11384", mode="replace"
        )
    )
    osw.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title="Category:OSWacdb001c926c46b998af3e645d36b13f", mode="append"
        )
    )
    osw.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title="Category:OSW51ad0d1716254c77a2b7a03217f23b43", mode="append"
        )
    )

# #explicit load host and server
# host = osw.load_entity("Item:OSWb8625aedf4074b72a4fa9bcb11694e4d")
# server = osw.load_entity("Item:OSW536e1417a0eb427887aeb267f47442fb")

db = osw.load_entity("Item:OSW837099bdc67d4b7cb5ffcce713a7648b")
db = db.cast(model.Database)

# #load host and server from references
# server = osw.load_entity(db.db_server)
# server = server.cast(model.DatabaseServer)
# host = osw.load_entity(server.host)
# host = host.cast(model.Host)

# #load host and server from semantic queries
server_title = wtsite.semantic_search(
    f"[[-HasDbServer::Item:{osw.get_osw_id(db.uuid)}]]"
)
server = osw.load_entity(server_title[0])

host_title = wtsite.semantic_search(f"[[-HasHost::Item:{osw.get_osw_id(server.uuid)}]]")
host = osw.load_entity(host_title[0])


connect_str = f"{host.network_domain[0]}:{server.network_port[0]}/{db.db_name}"
print(connect_str)

# cast into controller and execute function
# db = db.cast(controller.DbController)
# print(db.create_table())
