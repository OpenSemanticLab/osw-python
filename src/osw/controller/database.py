from typing import Optional, Union

from sqlalchemy import URL, create_engine
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Engine

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.core import OSW
from osw.model.static import OswBaseModel


class DatabaseController(model.Database):
    """
    Provides a sqlalchemy engine for the specified database
    """

    osw: Optional[OSW]
    """ an OSW instance to fetch related resources (host, server, etc.)"""
    cm: Optional[CredentialManager]
    """ CredentialManager to login to the database"""
    engine: Optional[Engine]
    """ the internal sqlalchemy engine """

    class Config:
        arbitrary_types_allowed = True

    class ConnectionString(OswBaseModel):
        """the sqlalchemy database connection string"""

        dialect: str
        """ sql subtype, e. g. postgres"""
        username: str
        """ username for the login """
        password: str
        """ password for the login """
        host: str
        """ the database host (ip address or domain) """
        port: int
        """ the database port """
        database: str
        """ the database name / identifier """
        driver: Optional[str]
        """ specific driver, e. g. psycopg2 """

        def __str__(self):
            """generates the string representation

            Returns
            -------
                database connection string
            """
            prefix = f"{self.dialect}"
            if self.driver:
                prefix += f"+{self.driver}"
            url = URL.create(
                prefix,
                username=self.username,
                password=self.password,
                host=self.host,
                port=self.port,
                database=self.database,
            )
            return url.render_as_string(hide_password=False)

    class ConnectionConfig(OswBaseModel):
        """Database connection configuration"""

        osw: OSW
        """ OSW instance to fetch related resources (host, server, etc.) """
        cm: Union[CredentialManager.Credential, CredentialManager]
        """ CredentialManager or direct Credential to login to the database"""

    def connect(self, config: ConnectionConfig):
        """Initializes the connection to the database by creating a sqlalchemy engine

        Parameters
        ----------
        config
            see ConnectionConfig
        """
        self.osw = config.osw
        self.cm = config.cm

        server_title = self.osw.site.semantic_search(
            f"[[-HasDbServer::Item:{self.osw.get_osw_id(self.uuid)}]]"
        )
        server = self.osw.load_entity(server_title[0]).cast(model.DatabaseServer)

        host_title = self.osw.site.semantic_search(
            f"[[-HasHost::Item:{self.osw.get_osw_id(server.uuid)}]]"
        )
        host = self.osw.load_entity(host_title[0]).cast(model.Host)

        dbtype_title = self.osw.site.semantic_search(
            f"[[-HasDbType::Item:{self.osw.get_osw_id(server.uuid)}]]"
        )
        dbtype = self.osw.load_entity(dbtype_title[0]).cast(model.DatabaseType)

        if type(self.cm) is CredentialManager.Credential:
            db_server_cred = self.cm
        else:
            db_server_cred = config.cm.get_credential(
                CredentialManager.CredentialConfig(
                    iri=f"{host.network_domain[0]}:{server.network_port[0]}",
                    fallback=CredentialManager.CredentialFallback.ask,
                )
            )

        cstr = DatabaseController.ConnectionString(
            dialect=dbtype.connection_str_dialect,
            driver=dbtype.connection_str_driver,
            username=db_server_cred.username,
            password=db_server_cred.password,
            host=host.network_domain[0],
            port=server.network_port[0],
            database=self.name,
        )

        self.engine = create_engine(str(cstr))

    def execute(self, sql: str):
        """Executes a plain sql string

        Parameters
        ----------
        sql
            the sql string
        """
        with self.engine.connect() as conn:
            result_set = conn.execute(sql_text(sql))
            for r in result_set:
                print(r)
