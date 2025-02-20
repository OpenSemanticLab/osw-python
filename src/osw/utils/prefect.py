"""Prefect utils as support for OpenSemanticWorld."""

import asyncio
import re
import sys
from datetime import timedelta
from importlib.metadata import version
from typing import Iterable, List, Optional

from packaging.specifiers import SpecifierSet
from prefect import Flow, get_client, serve
from prefect.blocks.notifications import MicrosoftTeamsWebhook
from prefect.client.schemas.objects import FlowRun
from prefect.settings import PREFECT_API_URL
from prefect.states import State
from pydantic import BaseModel, SecretStr

# from prefect.settings import PREFECT_API_URL


# ------------------------------ NOTIFICATIONS ------------------------------
class NotifyTeamsParam(BaseModel):
    """Parameter set for notifying Microsoft Teams using class NotifyTeams"""

    teams_webhook_url: SecretStr
    """Microsoft Teams webhook URL containing a secret"""
    deployment_name: Optional[str] = None
    """Deployment name to be displayed in the notification"""


class NotifyTeams(NotifyTeamsParam):
    """Notify Microsoft Teams channel using a webhook"""

    def __init__(self, notify_teams_param: NotifyTeamsParam):
        super().__init__(**notify_teams_param.model_dump())

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

        _message = f"📜 Message:\n\n_`{state.message}`_"

        # # DEBUG
        # print(_flow_run + _deployment + _ts + _tags + _message)
        # print(f"Teams webhook URL: {self.teams_webhook_url}")
        # print(f"Deployment name: {self.deployment_name}")
        # print(f"Flow name: {flow.name}")
        # print(f"Flow run name: {flow_run.name}")
        # print(f"Flow run ID: {flow_run.id}")

        MicrosoftTeamsWebhook(url=self.teams_webhook_url.get_secret_value()).notify(
            body=(_flow_run + _deployment + _ts + _tags + _message)
        )


# ------------------------------- DEPLOYMENTS -------------------------------
def tagsStrToList(tags: str) -> List[str]:
    """Remove tags whitespaces, newlines, tabs, empty strings, split comma"""
    return list(filter(None, re.sub(r"\s+", "", tags).split(",")))


class DeployConfig(BaseModel):
    """Prefect deployment configuration"""

    flow: Flow
    name: str | None = None
    description: str | None = None
    interval: Iterable[int | float | timedelta] | int | float | timedelta | None = None
    cron: Iterable[str] | str | None = None
    version: str | None = None
    tags: List[str] | None = None

    # Parameters that could be added in future, see to_deployment function:
    # rrule: Iterable[str] | str | None = None
    # paused: bool | None = None
    # schedules: List[FlexibleScheduleList] | None = None
    # schedule: SCHEDULE_TYPES | None = None
    # is_schedule_active: bool | None = None
    # parameters: dict | None = None
    # triggers: List[DeploymentTriggerTypes | TriggerTypes] | None = None
    # enforce_parameter_schema: bool = False
    # work_pool_name: str | None = None
    # work_queue_name: str | None = None
    # job_variables: Dict[str, Any] | None = None
    # deployment_id: str | None = None
    # prefect_api_url: str = PREFECT_API_URL
    class Config:
        arbitrary_types_allowed = True


class DeployParam(BaseModel):
    """Parameter set for deploying flows as deployments"""

    deployments: List[DeployConfig]
    """List of deployments to be served"""
    # TODO: Implement remove_existing_deployments
    remove_existing_deployments: Optional[bool] = False
    """Will remove existing deployments of the specified flows/software"""
    # TODO: Add parameter for OSW support in next version


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
        config = await flow.to_deployment(
            name=deploy_config.name,
            tags=deploy_config.tags,
            cron=deploy_config.cron,
            interval=deploy_config.interval,
            description=deploy_config.description,
            version=deploy_config.version,
        )
        await config.apply()  # returns the deployment_uuid

        deployments.append(config)

        # fetch flow uuid
        async with get_client() as client:
            response = await client.read_flow_by_name(flow.name)
            print(response.json())
            flow_uuid = response.id
        print("Flow UUID:", flow_uuid)

        # prefect_domain = (
        #     environ.get("PREFECT_API_URL").split("//")[-1].split("/")[0]
        # )  # noqa
        # print("Prefect domain:", prefect_domain)
        # start agent to serve deployment
        # await deploy_config.flow.serve(name=deployment_name)
    if version("prefect") in SpecifierSet(">=3.0"):
        return deployments
    else:
        await serve(*deployments)


def deploy(param: DeployParam):
    """Function to serve configured flows as deployments by python version."""
    if sys.version_info >= (3, 11):
        # python >= 3.11
        with asyncio.Runner() as runner:
            deployments = runner.run(_deploy(param))
    else:
        # python < 3.11
        deployments = asyncio.run(_deploy(param))
    if version("prefect") in SpecifierSet(">=3.0"):
        serve(*deployments)
