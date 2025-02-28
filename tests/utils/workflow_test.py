"""Test workflows for `osw-python` package"""

import subprocess
from os import environ

import pytest
from prefect import flow
from prefect.testing.utilities import prefect_test_harness
from pydantic import SecretStr

from osw.utils.workflow import (
    DeployConfig,
    DeployParam,
    NotifyTeams,
    NotifyTeamsParam,
    _deploy,
    deploy,
    tags_str_to_list,
)


# ------------------------------ NOTIFICATIONS ---------------------
@flow(
    # Microsoft Teams notification on completion for testing
    # Notification only if env var
    on_completion=[
        NotifyTeams(
            NotifyTeamsParam(
                teams_webhook_url=SecretStr(environ.get("TEAMS_WEBHOOK_URL")),
                # OPTIONAL, will be empty if no deploment is assigned
                deployment_name="osw-python-notify-teams-test",
            )
        ).notify_teams
    ],
    log_prints=True,
)
@flow
def osw_python_teams_notify_test_flow():
    """Notify Microsoft Teams channel using a webhook"""
    return 42


def test_notify_teams():
    """Test of flow to notify Microsoft Teams channel using a webhook"""
    with prefect_test_harness():
        test_flow_run = osw_python_teams_notify_test_flow()
        assert test_flow_run == 42


# ------------------------------- DEPLOYMENTS -------------------------------
def test_tags_str_to_list(tags="osw-python,example-deploy-flow"):
    """Test of conversion of tags string to list"""
    assert tags_str_to_list("osw-python,example-deploy-flow") == [
        "osw-python",
        "example-deploy-flow",
    ]


@flow
def osw_python_test_flow_to_deploy():
    """Example flow to be deployed"""
    print(f"Execution of example: {osw_python_test_flow_to_deploy.__name__}!")


deploy_param = DeployParam(
    deployments=[
        DeployConfig(
            flow=osw_python_test_flow_to_deploy,
            name="osw-python-deployment-test",
            description="Deployment of osw-python test flow",
            version="0.0.1",
            tags=["osw-python", "example-deploy-flow"],
        )
    ],
    # remove_existing_deployments=True,
)


@pytest.mark.asyncio
async def test_deploy_serve():
    """Test of deployment of example flow"""
    with prefect_test_harness():
        _deploy(param=deploy_param)


@pytest.mark.skip(reason="Not deployable in test environment")
def test_deploy_runner():
    """Test of deployment of example flow"""
    with prefect_test_harness():
        # test environment shell:
        command = "prefect config set PREFECT_API_URL=http://127.0.0.1:8443/api"
        subprocess.run(command, shell=True)
        # Not deployable in local test environment
        deploy(param=deploy_param)
