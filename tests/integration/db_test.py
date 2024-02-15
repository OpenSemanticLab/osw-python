import mwclient

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.core import OSW
from osw.wtsite import WtSite

# run with: tox -e test -- --wiki_domain domain --wiki_username user --wiki_password pass --db_username user --db_password pass


def _test_connection_string(
    wiki_domain, wiki_username, wiki_password, db_username, db_password
):
    # make sure to import controllers after updating the model (ignore linter warning)
    import osw.controller as controller  # noqa: E402

    cstr = controller.DatabaseController.ConnectionString(
        dialect="postgresql",
        driver="pg8000",
        username="dbuser",
        password="kx@jj5/g",
        host="pghost10",
        port="3000",
        database="appdb",
    )
    assert str(cstr) == "postgresql+pg8000://dbuser:kx%40jj5%2Fg@pghost10:3000/appdb"

    cstr = controller.DatabaseController.ConnectionString(
        dialect="postgresql",
        username="dbuser",
        password="kx@jj5/g",
        host="pghost10",
        port="3000",
        database="appdb",
    )
    assert str(cstr) == "postgresql://dbuser:kx%40jj5%2Fg@pghost10:3000/appdb"


def test_connect_and_query(
    wiki_domain, wiki_username, wiki_password, db_username, db_password
):
    site = mwclient.Site(host=wiki_domain)
    site.login(username=wiki_username, password=wiki_password)
    wtsite = WtSite(WtSite.WtSiteLegacyConfig(site=site))
    osw = OSW(site=wtsite)

    osw.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title="Category:OSW02590972aeba46d7864ed492c0c11384",  # Host
            mode="replace",
        )
    )
    osw.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title="Category:OSWacdb001c926c46b998af3e645d36b13f",
            # DatabaseServer
            mode="append",
        )
    )
    osw.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title="Category:OSW51ad0d1716254c77a2b7a03217f23b43",  # Database
            mode="append",
        )
    )
    osw.fetch_schema(
        OSW.FetchSchemaParam(
            schema_title="Category:OSW33c7c3a4076a4a58b20d818c162e84e6",  # DatabaseType
            mode="append",
        )
    )

    # make sure to import controllers after updating the model (ignore linter warning)
    import osw.controller as controller  # noqa: E402

    # load database definition
    db = osw.load_entity("Item:OSWb8cc7705e17c47b19331fdb045bfbca8")  # postgres
    db = db.cast(model.Database)

    # cast into controller and execute function
    db = db.cast(controller.DatabaseController)
    db.connect(
        controller.DatabaseController.ConnectionConfig(
            cm=CredentialManager.UserPwdCredential(
                iri="", username=db_username, password=db_password
            ),
            osw=osw,
        )
    )
    db.execute("SELECT * FROM public.sensors ORDER BY sensor_id ASC")
