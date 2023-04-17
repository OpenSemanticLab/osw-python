import json
from datetime import datetime
from typing import Any, Dict, Optional, Union

import sqlalchemy
import sqlalchemy.dialects.postgresql as postgresql
from pydantic import PrivateAttr

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
    engine: Optional[sqlalchemy.Engine]
    """ the internal sqlalchemy engine """

    _tables: Dict[str, sqlalchemy.Table] = PrivateAttr()
    """ internal table cache """

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
            url = sqlalchemy.URL.create(
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

        self._tables = {}

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

        self.engine = sqlalchemy.create_engine(str(cstr))

    class ExecuteParam(OswBaseModel):
        """Param class for DatabaseController.execute"""

        stmt: Optional[Any]
        """a sqlalchemy statement"""
        sql: Optional[str]
        """a raw SQL string"""
        autocommit: Optional[bool] = True
        """autocommit INSERT and UPDATE statement"""

    def execute(self, param: ExecuteParam):
        """Executes a plain sql string

        Parameters
        ----------
        param
            see DatabaseController.ExecuteParam
        Returns
        -------
            CursorResult
        """
        stmt = None
        if param.sql is not None:
            param.stmt = param.sql
        if param.stmt is not None:
            stmt = param.stmt
            if type(param.stmt) == str:
                stmt = sqlalchemy.text(param.stmt)
        res = None
        if stmt is not None:
            with self.engine.connect() as conn:
                res = conn.execute(stmt)
                if (
                    param.autocommit
                    and type(stmt) != "sqlalchemy.sql.selectable.Select"
                ):
                    conn.commit()
        return res

    class TableExistsParam(OswBaseModel):
        """Param class for DatabaseController.table_exists"""

        name: str
        """the table name"""

    def table_exists(self, param: TableExistsParam):
        """Checks if a table already exits

        Parameters
        ----------
        param
            see DatabaseController.TableExistsParam
        Returns
        -------
            True if the table exists, else False
        """
        exists = False
        with self.engine.connect() as conn:
            exists = self.engine.dialect.has_table(conn, param.name)
        return exists

    def get_server_time(self):
        """Gets the current server time

        Returns
        -------
            datetime object
        """
        stmt = sqlalchemy.select(sqlalchemy.func.now())
        dt: datetime = self.execute(DatabaseController.ExecuteParam(stmt=stmt)).all()[
            0
        ][0]
        return dt


class TimescaleDbController(DatabaseController):
    """Specific subclass for a TimescaleDB"""

    def get_source_table(self):
        """Gets the mapping table for UUIDs and integer indices
           Creates a new table if not existing yet
        Returns
        -------
            the sources table object
        """
        table_name = "sources"
        if table_name in self._tables:
            return self._tables[table_name]

        exists = self.table_exists(DatabaseController.TableExistsParam(name=table_name))

        metadata_obj = sqlalchemy.MetaData()
        table = sqlalchemy.Table(
            table_name,
            metadata_obj,
            sqlalchemy.Column(
                "index", sqlalchemy.INTEGER, primary_key=True, autoincrement="auto"
            ),
            sqlalchemy.Column(
                "uuid", sqlalchemy.String(40), nullable=False, unique=True, index=True
            ),
        )
        # sqlalchemy.Index("sources1_uuid_index", table.c.uuid) #manual index
        # jsonb index see https://stackoverflow.com/questions/30885846/how-to-create-jsonb-index-using-gin-on-sqlalchemy

        if not exists:
            print(f"Create table '{table_name}'")
            metadata_obj.create_all(self.engine)
        else:
            print(f"Table '{table_name}' already exists")

        self._tables[table_name] = table
        return table

    def get_source_index(self, source: model.DataSource):
        """get the index of a given data source UUID

        Parameters
        ----------
        uuid
            the data source UUID

        Returns
        -------
            the index from the sources table
        """

        sources = self.get_source_table()
        uuid = str(source.uuid)

        stmt = sources.select().where(sources.c.uuid == uuid)
        res = self.execute(DatabaseController.ExecuteParam(stmt=stmt)).all()
        if len(res):
            print("Found")
            print(res[0][0])
            return res[0][0]
        else:
            print("Insert")
            stmt = (
                postgresql.insert(sources).values(uuid=uuid)
                # .on_conflict_do_nothing() #will increment autoincrement index anyway
            )
            res = self.execute(DatabaseController.ExecuteParam(stmt=stmt))
            print(res.inserted_primary_key[0])
            return res.inserted_primary_key[0]

    def get_tool_table(self, tool: model.DataTool):
        """Gets the tool table for the given tool
           Creates a new table if not existing yet

        Parameters
        ----------
        tool
            a model.DataTool

        Returns
        -------
            the tool table object
        """

        table_name = self.osw.get_osw_id(tool.uuid).lower()
        if table_name in self._tables:
            return self._tables[table_name]

        exists = self.table_exists(DatabaseController.TableExistsParam(name=table_name))

        sources = self.get_source_table()

        metadata_obj = sqlalchemy.MetaData()
        table = sqlalchemy.Table(
            table_name,
            metadata_obj,
            sqlalchemy.Column(
                "time",
                postgresql.TIMESTAMP(timezone=True),
                default=sqlalchemy.func.now(),
                nullable=False,
            ),
            sqlalchemy.Column(
                "source_index",
                postgresql.INTEGER,
                sqlalchemy.ForeignKey(sources.c.index),
                nullable=False,
            ),
            sqlalchemy.Column("data", postgresql.JSONB),
        )

        if not exists:
            print(f"Create tool table '{table_name}'")
            metadata_obj.create_all(self.engine)
            print(f"Create hypertable for tool table '{table_name}'")
            stmt = sqlalchemy.select(
                sqlalchemy.func.create_hypertable(table_name, "time")
            )
            self.execute(DatabaseController.ExecuteParam(stmt=stmt))
        else:
            print(f"Tool table '{table_name}' already exists")

        self._tables[table_name] = table
        return table

    class InsertToolDataParam(OswBaseModel):
        """Param class to insert new data in a tool table with insert_tool_data()"""

        tool: model.DataTool
        """the tool owning the data source"""
        source: model.DataSource
        """the data source, e. g. a sensor"""
        data: model.Dataset
        """the data as instance of a dataset schema"""
        timestamp: Optional[datetime]
        """UTC timestamp of the data. Auto-created if not provided"""

    def insert_tool_data(self, param: InsertToolDataParam):
        """Inserts a new data set

        Parameters
        ----------
        param
            see InsertToolDataParam
        """
        tool = self.get_tool_table(param.tool)
        index = self.get_source_index(param.source)
        time = sqlalchemy.func.now()
        if param.timestamp:
            time = param.timestamp
        stmt = postgresql.insert(tool).values(
            # time=get_server_time(),
            # time=sqlalchemy.func.now(),
            time=time,
            source_index=index,
            data=json.loads(param.data.json(exclude_none=True)),
        )
        self.execute(DatabaseController.ExecuteParam(stmt=stmt))

    class QueryToolDataParam(OswBaseModel):
        """Param class to query for data in a tool table with query_tool_data()"""

        tool: model.DataTool
        """the tool owning the data"""
        source: model.DataSource
        """the data source, e. g. sensor"""
        min_time: Optional[datetime]
        """the minimal timestamp, older entries are ignored"""
        max_time: Optional[datetime]
        """the maximal timestamp, newer entries are ignored"""
        limit: Optional[int]

    def query_tool_data(self, param: QueryToolDataParam):
        """uery for data in a tool table

        Parameters
        ----------
        param
            see QueryToolDataParam

        Returns
        -------
            sqlalchemy query result
        """
        tool = self.get_tool_table(param.tool)
        index = self.get_source_index(param.source)
        stmt = sqlalchemy.select(tool)
        stmt = stmt.where(tool.c.source_index == index)
        if param.min_time:
            stmt = stmt.where(tool.c.time >= param.min_time)
        if param.max_time:
            stmt = stmt.where(tool.c.time <= param.max_time)
        res = self.execute(DatabaseController.ExecuteParam(stmt=stmt))
        param.source
        return res.all()
