"""Controller for the Postgrest API connected with TimescaleDB with specific database schema version."""

from typing import TYPE_CHECKING
from pathlib import Path

# from osw.core import OSW
from osw.params import LoadEntityParam

# from osw.defaults import paths, params
from osw.express import import_with_fallback, OswExpress
from pprint import pprint

wiki_domain__ = "wiki-dev.open-semantic-lab.org"
cred_filepath__ = Path(r"accounts.pwd.yaml")
osw_obj = OswExpress(domain=wiki_domain__, cred_filepath=cred_filepath__)
import_with_fallback(
    {
        "DatabaseServer": "Category:OSWacdb001c926c46b998af3e645d36b13f",  # TODO: Check if needed
        "Database": "Category:OSW51ad0d1716254c77a2b7a03217f23b43",
        "WebApi": "Category:OSW20bb1ff7501c401f857be671617e0e84",
        "DataTool": "Category:OSWda27e2fff10848ebb728ffb69c49a16d",
    },
    globals(),
    osw_express=osw_obj,
)
if TYPE_CHECKING:
    from osw.model.entity import Database  # , WebApi, DataTool

# TODO: to be removed
JWT = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYXBpX3VzZXIifQ.Sz2QvAGBhvkjrVfnH57rd5BH9R1duFtyDaullxxUDHI"


# 1 TODO: Entrypoint definition -> Device which is DataTool
# 2 TODO:

# class TimescaledbPostgrestController:
#     """"""
#     pass


def main(
    osw_domain="wiki-dev.open-semantic-lab.org",
    auth_upd_osw: bool = False,
) -> None:
    """Main function."""

    # Download Example Items
    _data_tool: Database = osw_obj.load_entity(
        LoadEntityParam(titles=["Item:OSWfea8fbbf39a441cfbc94677b0be2877d"])
    ).entities[0]
    pprint(_data_tool)


if __name__ == "__main__":
    # Update the local OSW model with the required schemas
    main(auth_upd_osw=True)
