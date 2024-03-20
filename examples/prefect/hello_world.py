from os import environ
from typing import Optional
from uuid import UUID, uuid4

from prefect import flow, task
from prefect.blocks.system import Secret
from pydantic import Field

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.core import OSW
from osw.wtsite import WtSite


class ConnectionSettings(model.OswBaseModel):
    osw_user_name: Optional[str]
    osw_domain: Optional[str]


@task
def connect(settings: ConnectionSettings):
    global wtsite
    # define username
    if environ.get("OSW_USER") is not None and environ.get("OSW_USER") != "":
        settings.osw_user_name = environ.get("OSW_USER")
    if environ.get("OSW_SERVER") is not None and environ.get("OSW_SERVER") != "":
        settings.osw_domain = environ.get("OSW_SERVER")
    password = ""
    if environ.get("OSW_PASSWORD") is not None and environ.get("OSW_PASSWORD") != "":
        password = environ.get("OSW_PASSWORD")
    else:
        # fetch secret stored in prefect server from calculated name
        password = Secret.load(
            settings.osw_user_name.lower() + "-" + settings.osw_domain.replace(".", "-")
        ).get()  # e. g. mybot-wiki-dev-open-semantic-lab-org
    cm = CredentialManager()
    cm.add_credential(
        CredentialManager.UserPwdCredential(
            iri=settings.osw_domain, username=settings.osw_user_name, password=password
        )
    )
    wtsite = WtSite(WtSite.WtSiteConfig(iri=settings.osw_domain, cred_mngr=cm))
    global osw
    osw = OSW(site=wtsite)


@task
def fetch_schema():
    # osw.fetch_schema() #this will load the current entity schema from the OSW instance.
    # You may have to re-run the script to get the updated schema extension.
    # Requires 'pip install datamodel-code-generator'
    # Load Article Schema on demand
    if not hasattr(model, "Article"):
        osw.fetch_schema(
            OSW.FetchSchemaParam(
                schema_title="Category:OSW92cc6b1a2e6b4bb7bad470dfdcfdaf26",
                mode="replace",
            )
        )


class Result(model.OswBaseModel):
    uuid: Optional[UUID] = UUID("56f9439d-4324-4fe7-a831-63bab9414ee1")
    msg: str


@task
def store_and_document_result(result: Result):
    print(result)
    title = "Item:" + osw.get_osw_id(result.uuid)
    entity = osw.load_entity(title)
    if entity is None:
        # does not exist yet - create a new one
        entity = model.Article(
            uuid=result.uuid, label=[model.Label(text="Article for dummy workflow")]
        )

    # edit structured data
    entity = entity.cast(model.Article)
    entity.description = model.Description(text="some descriptive text")
    osw.store_entity(entity)

    # edit unstructured data (ToDo: access page directly from entity)
    page = osw.site.get_page(WtSite.GetPageParam(titles=[title])).pages[0]
    page.set_slot_content(
        slot_key="main", content=page.get_slot_content("main") + "<br>\n" + result.msg
    )
    page.edit()
    print("FINISHED")


class Request(model.OswBaseModel):
    uuid: UUID = Field(default_factory=uuid4, title="UUID")
    osw_domain: Optional[str] = "wiki-dev.open-semantic-lab.org"
    msg: str


@flow()
def dummy_workflow(request: Request):
    connect(ConnectionSettings(osw_domain=request.osw_domain))
    fetch_schema()
    store_and_document_result(Result(msg=request.msg))


if __name__ == "__main__":
    dummy_workflow(Request(msg="Test"))
    # programmatic deployment supported in newer prefect versions
    # dummy_workflow.serve(
    #    name="dummy-workflow-deployment"
    # )
