"""Prefect utils as support for OpenSemanticWorld."""

import asyncio
import re
import sys
import uuid as uuid_module
from datetime import timedelta
from importlib.metadata import version
from inspect import signature
from os import environ
from typing import Any, Dict, Iterable, List, Optional, Union
from uuid import UUID

from packaging.specifiers import SpecifierSet
from prefect import Flow, get_client, serve
from prefect.blocks.notifications import MicrosoftTeamsWebhook
from prefect.blocks.system import Secret
from prefect.client.schemas.objects import FlowRun
from prefect.settings import PREFECT_API_URL
from prefect.states import State
from pydantic import SecretStr
from pydantic.v1 import BaseModel

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.core import OSW
from osw.utils.wiki import get_full_title
from osw.wtsite import WtSite


# ------------------------------ CONNECTION ---------------------
class ConnectionSettings(BaseModel):
    """Connection data for OSW.

    If osw_user_name or osw_domain are not provided, they are read from
    environment variables OSW_USER and OSW_SERVER respectively.
    """

    osw_user_name: Optional[str] = None
    """The login username. Falls back to env var OSW_USER."""
    osw_domain: Optional[str] = None
    """The domain of the instance. Falls back to env var OSW_SERVER."""


def connect(settings: Optional[ConnectionSettings] = None) -> OSW:
    """Connect to an OSW instance.

    Reads OSW_USER, OSW_SERVER, OSW_PASSWORD from environment variables.
    If OSW_PASSWORD is not set, falls back to a Prefect Secret named
    ``<username>-<domain-with-dashes>`` (e.g. ``mybot-wiki-dev-open-semantic-lab-org``).

    Parameters
    ----------
    settings
        Optional connection settings. If None, all values come from env vars.

    Returns
    -------
    OSW
        A connected OSW instance.
    """
    if settings is None:
        settings = ConnectionSettings()
    if environ.get("OSW_USER"):
        settings.osw_user_name = environ["OSW_USER"]
    if environ.get("OSW_SERVER"):
        settings.osw_domain = environ["OSW_SERVER"]
    password = environ.get("OSW_PASSWORD", "")
    if not password:
        # fetch secret stored in prefect server from calculated name
        password = Secret.load(
            settings.osw_user_name.lower() + "-" + settings.osw_domain.replace(".", "-")
        ).get()
    cm = CredentialManager()
    cm.add_credential(
        CredentialManager.UserPwdCredential(
            iri=settings.osw_domain,
            username=settings.osw_user_name,
            password=password,
        )
    )
    wtsite = WtSite(WtSite.WtSiteConfig(iri=settings.osw_domain, cred_mngr=cm))
    return OSW(site=wtsite)


# ------------------------------ REQUESTS ---------------------
class WorkflowRequest(BaseModel):
    """Base request model for OSW Prefect workflows.

    Provides common fields for provenance tracking and targeting.
    Extend this class with workflow-specific fields.
    """

    uuid: UUID = None
    """UUIDv4 of the request (for provenance tracking)."""
    osw_domain: Optional[str] = None
    """The domain of the OSW instance. Falls back to env var OSW_SERVER."""
    subject: Optional[str] = None
    """The target page title to associate results with."""

    class Config:
        arbitrary_types_allowed = True


# ------------------------------ NOTIFICATIONS ---------------------
class NotifyTeamsParam(BaseModel):
    """Parameter set for notifying Microsoft Teams using class NotifyTeams"""

    teams_webhook_url: SecretStr
    """Microsoft Teams webhook URL containing a secret"""
    deployment_name: Optional[str] = None
    """Deployment name to be displayed in the notification"""

    # allow arbitrary types for compatibility with pydantic v1
    class Config:
        arbitrary_types_allowed = True


class NotifyTeams(NotifyTeamsParam):
    """Notify Microsoft Teams channel using a webhook"""

    def __init__(self, notify_teams_param: NotifyTeamsParam):
        # super().__init__(**notify_teams_param.model_dump())  # pydantic v2
        super().__init__(**notify_teams_param.dict())  # pydantic v1

    def notify_teams(
        self,
        flow,
        flow_run: FlowRun,
        state: State,
    ):

        host_url = str(PREFECT_API_URL.value()).replace("/api", "")

        _flow_run = f"**🚨Flow Run: [{flow.name} > {flow_run.name}]({host_url}/flow-runs/flow-run/{flow_run.id}) ❗{state.name}❗**\n\n"  # noqa

        if flow_run.deployment_id is not None:
            # Assigned deployment found
            deployment_url = (
                f"{host_url}/deployments/deployment/{flow_run.deployment_id}"
            )
            if self.deployment_name == "" or self.deployment_name is None:
                _deployment = f"🚀 Deployment: _[{flow_run.deployment_id}]({deployment_url})_\n\n"  # noqa
            else:
                _deployment = f"🚀 Deployment: _[{self.deployment_name}]({deployment_url})_\n\n"  # noqa
        else:
            # No deployment assigned
            _deployment = "🚀 Deployment: _Just flow, no deployment_\n\n"

        _ts = f"🕑 Timestamp: _{flow_run.state.timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')}_\n\n"  # noqa
        if flow_run.tags != []:
            _tags = f"🏷️ Tags: _#{' #'.join(flow_run.tags)}_\n\n"
        else:
            _tags = ""

        if state.message is None:
            _message = "No message provided."
        else:
            _message = f"📜 Message:\n\n_`{state.message}`_"

        MicrosoftTeamsWebhook(
            url=str(self.teams_webhook_url.get_secret_value())
        ).notify(body=(_flow_run + _deployment + _ts + _tags + _message))


# ------------------------------- DEPLOYMENTS -------------------------------
def tags_str_to_list(tags: str) -> List[str]:
    """Remove tags whitespaces, newlines, tabs, empty strings, split comma"""
    return list(filter(None, re.sub(r"\s+", "", tags).split(",")))


# def filter_arguments(func, args_dict):
#     """Filter arguments for a function based on its signature"""
#     sig = signature(func)
#     valid_params = sig.parameters
#     filtered_args = {k: v for k, v in args_dict.items() if k in valid_params}
#     return filtered_args


def match_func_model_args(func, model: BaseModel) -> dict:
    """Match function arguments with model attributes"""
    valid_params = set(signature(func).parameters)
    # model_attrs = model.model_dump().items() # pydantic v2
    model_attrs = model.dict().items()  # pydantic v1
    matched_args = {k: v for k, v in model_attrs if k in valid_params}
    return matched_args


class DeployConfig(BaseModel):
    """Prefect deployment configuration"""

    flow: Flow  # to be excluded in `flow.to_deployment()` function
    # Union instead of | for compatibility with pydantic v1, python < 3.10
    name: Union[str, None] = None
    description: Union[str, None] = None
    interval: Union[
        Iterable[Union[int, float, timedelta]], int, float, timedelta, None
    ] = None
    cron: Union[Iterable[str], str, None] = None
    version: Union[str, None] = None
    tags: Union[List[str], None] = None
    rrule: Union[Iterable[str], str, None] = None
    paused: Union[bool, None] = None
    is_schedule_active: Union[bool, None] = None
    parameters: Union[dict, None] = None
    enforce_parameter_schema: bool = False
    work_pool_name: Union[str, None] = None
    work_queue_name: Union[str, None] = None
    job_variables: Union[Dict[str, Any], None] = None
    deployment_id: Union[str, None] = None

    class Config:
        arbitrary_types_allowed = True


class DeployParam(BaseModel):
    """Parameter set for deploying flows as deployments"""

    deployments: List[DeployConfig]
    """List of deployments to be served"""
    # TODO: Implement remove_existing_deployments
    remove_existing_deployments: Optional[bool] = False
    """Will remove existing deployments of the specified flows/software"""
    osw: Optional[OSW] = None
    """If provided, deployed flows are registered as Software + PrefectFlow
    entities on the OSW instance."""
    namespace_uuid: Optional[UUID] = None
    """Static UUIDv5 namespace for stable Software entity UUIDs.
    If None, a default namespace is used."""

    class Config:
        arbitrary_types_allowed = True


# Default UUIDv5 namespace for flow registration
_DEFAULT_NAMESPACE_UUID = uuid_module.UUID("0dd6c54a-b162-4552-bab9-9942ccaf4f41")


async def register_flow(
    osw_instance: OSW,
    flow: Flow,
    namespace_uuid: Optional[UUID] = None,
) -> None:
    """Register a Prefect flow as Software + PrefectFlow entities on OSW.

    Creates or updates:
    - A Software entity with a stable UUID (uuid5 from flow name)
    - A PrefectFlow entity with the UUID from the Prefect API

    Parameters
    ----------
    osw_instance
        A connected OSW instance.
    flow
        The Prefect Flow object to register.
    namespace_uuid
        UUIDv5 namespace for generating the Software entity UUID.
        If None, uses a default namespace.
    """
    if namespace_uuid is None:
        namespace_uuid = _DEFAULT_NAMESPACE_UUID

    # ensure required schemas are loaded (needed if entity.py is regenerated)
    if not hasattr(model, "Software") or not hasattr(model, "PrefectFlow"):
        osw_instance.fetch_schema(
            OSW.FetchSchemaParam(
                schema_title=[
                    "Category:OSW77e749fc598341ac8b6d2fff21574058",  # Software
                    "Category:OSW72eae3c8f41f4a22a94dbc01974ed404",  # PrefectFlow
                ],
                mode="replace",
            )
        )

    # fetch flow uuid from Prefect API
    async with get_client() as client:
        response = await client.read_flow_by_name(flow.name)
        flow_uuid = response.id

    # create Software entity
    this_tool = model.Software(
        uuid=uuid_module.uuid5(namespace_uuid, flow.name),
        label=[model.Label(text=flow.name)],
        description=[model.Description(text=flow.description or "")],
    )

    # create PrefectFlow entity
    prefect_api_url = environ.get("PREFECT_API_URL", "")
    prefect_domain = prefect_api_url.split("//")[-1].split("/")[0]
    this_flow = model.PrefectFlow(
        uuid=flow_uuid,
        label=[model.Label(text=flow.name + " Prefect Flow")],
        description=[model.Description(text=flow.description or "")],
        flow_id=str(flow_uuid),
        hosted_software=[get_full_title(this_tool)],
        domain=prefect_domain,
    )

    # delete stale PrefectFlow entities that reference the same Software
    # (avoids confusing the prefect.js reverse lookup)
    software_title = get_full_title(this_tool)
    stale_titles = osw_instance.site.semantic_search(f"[[Hosts::{software_title}]]")
    new_flow_title = "Item:" + OSW.get_osw_id(flow_uuid)
    stale_entities = []
    for title in stale_titles:
        if title != new_flow_title:
            entity = osw_instance.load_entity(title)
            if entity is not None:
                stale_entities.append(entity)
    if stale_entities:
        for e in stale_entities:
            print(
                f"WARNING: Deleting stale PrefectFlow entity "
                f"'{get_full_title(e)}' (superseded by '{new_flow_title}')"
            )
        osw_instance.delete_entity(
            stale_entities,
            comment="Replaced by updated PrefectFlow deployment",
        )

    osw_instance.store_entity(OSW.StoreEntityParam(entities=[this_tool, this_flow]))

    # build parameters template from flow function signature
    # includes all fields so users can see and customize them
    import inspect
    import json

    sig = inspect.signature(flow.fn)
    params_template = {}
    for name, param in sig.parameters.items():
        if param.default is not inspect.Parameter.empty:
            default = param.default
            if hasattr(default, "dict"):
                default = default.dict()
            params_template[name] = default
        elif param.annotation is not inspect.Parameter.empty:
            ann = param.annotation
            if hasattr(ann, "__fields__"):
                # pydantic model — show all fields with defaults or placeholders
                field_values = {}
                for fname, field in ann.__fields__.items():
                    if field.default_factory is not None:
                        field_values[fname] = f"<{fname}>"
                    elif field.default is not None:
                        field_values[fname] = field.default
                    else:
                        field_values[fname] = f"<{fname}>"
                params_template[name] = field_values
            else:
                params_template[name] = f"<{name}>"
        else:
            params_template[name] = f"<{name}>"

    params_json = json.dumps(params_template, default=str)

    # replace known values with wiki/mustache template variables
    wiki_var_replacements = {
        '"<uuid>"': '"{{uuid}}"',
        '"<subject>"': '"{{FULLPAGENAME}}"',
        '"<osw_domain>"': '"{{SERVERNAME}}"',
    }
    for placeholder, wiki_var in wiki_var_replacements.items():
        params_json = params_json.replace(placeholder, wiki_var)

    # write usage template snippet to the Software page's main slot
    snippet = (
        '<div class="PrefectStatusBadge" data-config=\'{'
        ' "uuid": "{{uuid}}",'
        f' "workflow_title": "{software_title}",'
        ' "parent": "{{FULLPAGENAME}}",'
        f' "parameters": {params_json}'
        "}'></div>"
    )
    usage_text = (
        "== Usage ==\n"
        "Insert this snippet in a page to trigger this workflow:\n"
        "<pre>\n"
        f"{snippet}\n"
        "</pre>\n"
    )
    print(f"DEBUG: Writing usage template to '{software_title}':\n{snippet}")

    page = osw_instance.site.get_page(
        WtSite.GetPageParam(titles=[software_title])
    ).pages[0]
    page.set_slot_content(slot_key="main", content=usage_text)
    page.edit()


async def _deploy(param: DeployParam):
    """programmatic deployment supported in newer prefect versions
    This should become part of osw-python
    """

    deployments = []

    for deploy_config in param.deployments:
        flow: Flow = deploy_config.flow
        # Set deployment name if not provided
        if deploy_config.name is None or deploy_config.name == "":
            deploy_config.name = flow.name + "-deployment"

        # Match valid args of flow.to_deployment and deploy_config
        kwargs = match_func_model_args(func=flow.to_deployment, model=deploy_config)
        # Set config via matching flow.to_deployment arguments
        config = await flow.to_deployment(**kwargs)
        await config.apply()  # returns the deployment_uuid

        deployments.append(config)

        # Register flow on OSW if an instance is provided
        if param.osw is not None:
            await register_flow(
                osw_instance=param.osw,
                flow=flow,
                namespace_uuid=param.namespace_uuid,
            )

    if version("prefect") in SpecifierSet(">=3.0"):
        print(f"prefect version IF: {version('prefect')}")
        # return deployments
        await serve(*deployments)
    else:
        print(f"prefect version ELSE: {version('prefect')}")
        await serve(*deployments)


def deploy(param: DeployParam):
    """Function to serve configured flows as deployments by python version."""
    if sys.version_info >= (3, 11):
        print(f"python version IF: {sys.version_info}")
        # python >= 3.11
        with asyncio.Runner() as runner:
            runner.run(_deploy(param))
    else:
        # python < 3.11
        print(f"python version ELSE: {sys.version_info}")
        asyncio.run(_deploy(param))


# # ------------------------------- TEST -------------------------------
# from prefect import flow


# @flow
# def osw_python_test_flow_to_deploy():
#     """Example flow to be deployed"""
#     print(f"Execution of example: {osw_python_test_flow_to_deploy.__name__}!")


# if __name__ == "__main__":
#     deploy(
#         DeployParam(
#             deployments=[
#                 DeployConfig(
#                     flow=osw_python_test_flow_to_deploy,
#                     name="osw-python-deployment-test",
#                     description="Deployment of osw-python test flow",
#                     version="0.0.1",
#                     tags=["osw-python", "example-deploy-flow"],
#                 )
#             ],
#             # remove_existing_deployments=True,
#         )
#     )
