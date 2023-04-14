from typing import TYPE_CHECKING, Union

from pydantic import BaseModel, Field, FilePath

# import osw.controller.entity as controller
import osw.model.entity as model
import osw.wiki_tools as wt

# from osw.core import OSW
from osw.wtsite import WtSite

if TYPE_CHECKING:
    from dataclasses import dataclass as _basemodel_decorator
else:
    _basemodel_decorator = lambda x: x  # noqa: E731


class Entity(model.Entity):
    def explain(self):
        print(f"Entity with label '{str(self.label[0].text)}'")


# model.Entity = Entity


class Hardware(model.Hardware, Entity):
    def run(self):
        self.explain()
        print(" is running")


# model.Hardware = Hardware


@_basemodel_decorator
class Connection(BaseModel):
    osw_cred_fp: Union[str, FilePath]  # yaml file with credentials for the osw
    # instance
    db_server_cred_fp: Union[str, FilePath]  # yaml file with credentials for
    # the
    # database
    # server
    data_base: model.Database  # (python object generated from an OSW instance of
    # Database)

    def get_connection_str(self):
        """
        Return
        ------
        result:
            Connection string for the database server
        """
        # USe context manager for the following
        # Connect to osw
        wtsite = WtSite.from_domain(
            domain="wiki-dev.open-semantic-lab.org", password_file=self.osw_cred_fp
        )
        # osw = OSW(site=wtsite)
        wtsite.enable_cache()
        # get some parts of the connection str (port, IP address, driver, dialect)
        # query the database, from there, query the database server, from there query
        # the host, from there get the IP address, port
        # from the database server, get the database type, from there get the driver
        # and dialect
        dialect = ""
        driver = ""
        port = ""
        host = ""  # ip address or domain
        database = ""

        # ---- end of context manager indentation ---

        # Get the credentials from the db_server_cred_fp yaml file

        db_server_cred = wt.read_credentials_from_yaml(self.db_server_cred_fp)
        # build the connection string
        if driver:
            return (
                f"{dialect}+{driver}://{db_server_cred['username']}:"
                f"{db_server_cred['password']}@{host}:{port}/{database}"
            )
        else:
            return (
                f"{dialect}://{db_server_cred['username']}:"
                f"{db_server_cred['password']}@{host}:{port}/{database}"
            )

    connection_str: str = Field(default_factory=get_connection_str)

    """
    Pydantic does the definition of the following __init__ for you!
    def __init__(
            self,
            osw_cred_fp: Union[str, FilePath],
            db_server_cred_fp: Union[str, FilePath],
            data_base: model.Database
    ):  # Pydantic basemodel doc --> default_factory
        super().__init__()
        self.osw_cred_fp = osw_cred_fp
        self.db_server_cred_fp = db_server_cred_fp
        self.data_base = data_base
        self.connection_str = self.get_connection_str()
    """

    def open_connection(self):
        pass
        # connection_str = self.connection_str
        # self.engine = create_engine(connection_str)
        # open connection


class DbController(model.Database):
    def __init__(self, database_osw_id: str):
        self.database = database_osw_id

    def create_table(self):
        connection_str = self.db_server
        return connection_str

    def build_connection_str(self):
        connection_str = self.create_table()
        return connection_str
