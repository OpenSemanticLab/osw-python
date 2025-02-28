"""Prefect utils as support for OpenSemanticWorld."""

import asyncio
import re
import sys
from datetime import timedelta
from importlib.metadata import version
from inspect import signature
from typing import Any, Dict, Iterable, List, Optional, Union

from packaging.specifiers import SpecifierSet
from prefect import Flow, serve
from prefect.blocks.notifications import MicrosoftTeamsWebhook
from prefect.client.schemas.objects import FlowRun
from prefect.settings import PREFECT_API_URL
from prefect.states import State
from pydantic import SecretStr
from pydantic.v1 import BaseModel


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

        # Match valid args of flow.to_deployment and deploy_config
        kwargs = match_func_model_args(func=flow.to_deployment, model=deploy_config)
        # Set config via matching flow.to_deployment arguments
        config = await flow.to_deployment(**kwargs)
        await config.apply()  # returns the deployment_uuid

        deployments.append(config)

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
